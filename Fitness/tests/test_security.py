"""Local web server protections (DNS rebinding, CSRF, headers, file serving, SQL)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.main import app

ROOT = Path(__file__).resolve().parent.parent
local = TestClient(app, base_url="http://127.0.0.1:8000")


# ---- DNS rebinding: wrong Host header is refused ----

@pytest.mark.parametrize("host", ["attacker.example", "127.0.0.1.attacker.example", "192.168.1.5:8000", "evil:8000"])
def test_foreign_host_refused(host):
    r = local.get("/api/coach/insights", headers={"Host": host})
    assert r.status_code == 421


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "[::1]:8000", "localhost"])
def test_loopback_hosts_allowed(host):
    assert local.get("/api/health", headers={"Host": host}).status_code == 200


# ---- CSRF: writes from other sites are refused ----

def test_cross_site_write_refused_even_without_body():
    r = local.post("/api/running/garmin/1/skip", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = local.post("/api/import/batches/1/undo", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_same_origin_write_allowed():
    r = local.post("/api/running/garmin/1/skip", headers={"Origin": "http://127.0.0.1:8000", "Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 200


def test_cross_site_read_still_cannot_be_used_by_other_sites():
    r = local.get("/api/coach/insights", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers  # CORS: no permission to read
    assert r.headers["cross-origin-resource-policy"] == "same-origin"


# ---- Headers ----

def test_security_headers_everywhere():
    r = local.get("/api/health")
    for header in ("x-content-type-options", "x-frame-options", "referrer-policy", "cross-origin-resource-policy"):
        assert header in r.headers


def test_dashboard_has_strict_csp():
    if not (main.FRONTEND_DIST / "index.html").is_file():
        pytest.skip("frontend not built")
    r = local.get("/workouts")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-eval" not in csp


# ---- File serving: no path traversal ----

@pytest.mark.parametrize("path", ["../backend/main.py", "..%2F..%2F.env", "%2e%2e/%2e%2e/.env", "assets/../../src/paths.py"])
def test_no_path_traversal(path):
    if not (main.FRONTEND_DIST / "index.html").is_file():
        pytest.skip("frontend not built")
    r = local.get(f"/{path}")
    assert "import" not in r.text[:200] and "GARMIN" not in r.text
    assert r.headers["content-type"].startswith(("text/html", "application/json"))


def test_unknown_api_path_is_json_404():
    assert local.get("/api/does-not-exist").status_code == 404


def test_api_docs_off_by_default():
    assert "swagger" not in local.get("/docs").text.lower()
    assert '"openapi"' not in local.get("/openapi.json").text


# ---- Code-level checks ----

def test_sql_is_parameterized():
    """f-string SQL only interpolates column names from fixed allow-lists, never user values."""
    offenders = []
    for path in list((ROOT / "src").glob("*.py")) + list((ROOT / "backend").rglob("*.py")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'f"[^"]*\b(SELECT|INSERT|UPDATE|DELETE)\b', line) and "{" in line:
                allowed = ("cols", "placeholders", "updates", "table", "col", "int(limit)")
                inner = re.findall(r"\{([^}]*)\}", line)
                if "for c in cols" in line:  # column names from an allow-list
                    continue
                if not all(any(a in expr for a in allowed) for expr in inner):
                    offenders.append(f"{path.name}:{n}")
    assert offenders == []


def test_frontend_never_renders_raw_html():
    src = ROOT / "frontend" / "src"
    hits = [p.name for p in list(src.rglob("*.tsx")) + list(src.rglob("*.ts"))
            if re.search(r"dangerouslySetInnerHTML|\.innerHTML\s*=|\beval\(", p.read_text())]
    assert hits == []
