"""HTTP-level protections applied to every API response and request.

- Security headers: no MIME sniffing, no framing (clickjacking), no referrer leakage,
  a restrictive CSP for API responses (they are JSON, never pages), and HSTS outside
  development (production is served over HTTPS only).
- Request body limit: rejects bodies above ``max_bytes`` before they are read, so a
  client cannot tie up the server with huge uploads. The largest legitimate body is a
  saved flight offer (a few tens of KB).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

API_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Resource-Policy": "same-site",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, hsts: bool):
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # The interactive docs (development only) need their own scripts and styles.
        is_docs = request.url.path in ("/docs", "/redoc") or request.url.path.startswith("/docs/")
        for name, value in API_HEADERS.items():
            if is_docs and name == "Content-Security-Policy":
                continue
            response.headers.setdefault(name, value)
        if self.hsts:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class BodySizeLimitMiddleware:
    """Pure ASGI so oversized bodies are refused from the Content-Length header, or while
    streaming when no length is declared, without buffering them first."""

    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                await self._reject(scope, receive, send)
                return
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _TooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse({"detail": "Request body is too large."}, status_code=413)
        await response(scope, receive, send)


class _TooLarge(Exception):
    pass
