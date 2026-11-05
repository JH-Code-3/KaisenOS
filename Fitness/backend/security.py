"""
Local web server protections.

The app runs on 127.0.0.1 only, but a website open in your browser can
still try to reach it. These checks stop that:

- Host check (DNS rebinding): only requests addressed to 127.0.0.1,
  localhost or [::1] are answered. A malicious site that points its own
  domain at 127.0.0.1 is refused because its Host header is wrong.
- Origin check (CSRF): requests that change data must come from this
  app's own pages. Cross-site writes are refused even when they're the
  "simple" kind browsers send without asking first.
- Security headers on every response, and a strict Content Security
  Policy for the dashboard pages.
"""

import os
from urllib.parse import urlparse

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# The app's own pages: served by the backend (port 8000) or the Vite dev server (5173).
_PORT = os.environ.get("KAISEN_PORT", "8000")
ALLOWED_ORIGINS = {
    f"http://127.0.0.1:{_PORT}",
    f"http://localhost:{_PORT}",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
]

# React renders text safely; inline style attributes are used by the UI and
# charts, so styles allow 'unsafe-inline'. Scripts only from this app.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"
).encode()


def _host_allowed(host_header: str) -> bool:
    host = host_header.strip().lower()
    if host.startswith("["):  # [::1]:8000
        host = host.split("]")[0] + "]"
    else:
        host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    if host in LOOPBACK_HOSTS:
        return True
    # The test client uses "testserver"; only accepted when tests opt in.
    return host == "testserver" and os.environ.get("KAISEN_ALLOW_TEST_HOST") == "1"


def _origin_allowed(origin: str) -> bool:
    parsed = urlparse(origin)
    return f"{parsed.scheme}://{parsed.netloc}".lower() in ALLOWED_ORIGINS


class LocalOnlyMiddleware:
    """Pure ASGI middleware: host + origin checks, security headers."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}

        if not _host_allowed(headers.get("host", "")):
            return await _reject(send, 421, b"Requests must be addressed to 127.0.0.1 or localhost.")

        if scope["method"] not in SAFE_METHODS:
            origin = headers.get("origin")
            fetch_site = headers.get("sec-fetch-site")
            if (origin and not _origin_allowed(origin)) or fetch_site == "cross-site":
                return await _reject(send, 403, b"Cross-site requests can't change your data.")

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers += SECURITY_HEADERS
                content_type = next((v for k, v in response_headers if k.lower() == b"content-type"), b"")
                if content_type.startswith(b"text/html"):
                    response_headers.append((b"content-security-policy", CONTENT_SECURITY_POLICY))
                message = {**message, "headers": response_headers}
            await send(message)

        return await self.app(scope, receive, send_with_headers)


async def _reject(send, status: int, body: bytes):
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"text/plain; charset=utf-8"), *SECURITY_HEADERS],
    })
    await send({"type": "http.response.body", "body": body})
