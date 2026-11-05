"""
Privacy guardrails: only garmin_sync.py may use the internet, and the
only other network client allowed is the localhost-only Ollama wrapper.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NETWORK_MODULES = r"(httpx|requests|urllib\.request|urllib3|http\.client|socket|aiohttp|websockets|ollama|dotenv)"
IMPORT_RE = re.compile(rf"^\s*(?:import|from)\s+{NETWORK_MODULES}\b", re.M)

ALLOWED = {
    "garmin_sync.py": {"httpx", "dotenv"},
    "src/local_llm.py": {"ollama"},
    "run.py": {"socket"},  # only checks whether 127.0.0.1:<port> is already in use
}


def python_files():
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "tests/", "frontend/")) or "/node_modules/" in rel:
            continue
        yield rel, path.read_text()


def test_only_allowed_files_import_network_code():
    offenders = []
    for rel, text in python_files():
        for match in IMPORT_RE.finditer(text):
            module = match.group(1).split(".")[0]
            if module not in ALLOWED.get(rel, set()):
                offenders.append(f"{rel}: {match.group(0).strip()}")
    assert offenders == [], "Network code outside garmin_sync.py / local_llm.py:\n" + "\n".join(offenders)


def test_no_python_file_talks_to_a_non_local_url_except_garmin_sync():
    url_re = re.compile(r"https?://([A-Za-z0-9.\-\[\]:]+)")
    offenders = []
    for rel, text in python_files():
        if rel == "garmin_sync.py":
            continue
        for host in url_re.findall(text):
            if not host.startswith(("localhost", "127.0.0.1", "[::1]")):
                offenders.append(f"{rel}: {host}")
    assert offenders == []


def test_frontend_only_calls_local_backend():
    src = ROOT / "frontend" / "src"
    offenders = []
    for path in list(src.rglob("*.ts")) + list(src.rglob("*.tsx")) + [ROOT / "frontend" / "index.html"]:
        for host in re.findall(r"https?://([A-Za-z0-9.\-]+)", path.read_text()):
            if host not in ("127.0.0.1", "localhost"):
                offenders.append(f"{path.relative_to(ROOT)}: {host}")
    assert offenders == []


def test_garmin_sync_never_touches_workout_log():
    text = (ROOT / "garmin_sync.py").read_text() + (ROOT / "src" / "garmin_store.py").read_text()
    # No workout-log path in a string literal, and no workout-log imports.
    assert not re.search(r"""["'][^"'\n]*athlete""", text)
    assert not re.search(r"^\s*(from|import)\s+src\.(database|database_v2)\b", text, re.M)


def test_secrets_are_gitignored():
    ignore = (ROOT.parent / ".gitignore").read_text().splitlines()
    for pattern in (".env", "garmin_data.*", "*.db", "*.sqlite", "Fitness/data/", "*.log"):
        assert pattern in ignore, f"{pattern} missing from .gitignore"


def test_claude_code_cannot_read_env():
    import json

    settings = json.loads((ROOT.parent / ".claude" / "settings.json").read_text())
    assert "Read(./.env)" in settings["permissions"]["deny"]
