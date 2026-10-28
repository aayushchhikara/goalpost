"""Keep the unauthenticated local API out of reach of websites open in the user's browser.

Two checks run before any route:

- Host: only hosts on the allow list are served. A DNS-rebinding page reaches 127.0.0.1 under
  its own domain name, so its requests carry a foreign Host header and are refused.
- Origin: a state-changing request (anything but GET, HEAD, OPTIONS) that carries an Origin
  other than the frontend's is refused. CORS only hides responses from other sites; it doesn't
  stop a "simple" cross-site POST from running. Requests without an Origin (curl, scripts,
  server-side calls) aren't sent by browsers cross-site, so they pass.
"""

from collections.abc import Iterable

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from goalpost.schemas.errors import ErrorResponse

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _hostname(host_header: str) -> str:
    """The host without its port: "localhost:8000" → "localhost", "[::1]:8000" → "::1"."""
    if host_header.startswith("["):
        return host_header[1:].split("]", 1)[0].lower()
    return host_header.split(":", 1)[0].lower()


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, details=[])
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


class LocalOnlyMiddleware:
    def __init__(
        self, app: ASGIApp, *, allowed_hosts: Iterable[str], allowed_origins: Iterable[str]
    ) -> None:
        self.app = app
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self.allowed_origins = frozenset(o.rstrip("/") for o in allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        host = _hostname(headers.get("host", ""))
        origin = headers.get("origin")
        if host not in self.allowed_hosts:
            response = _error(400, "invalid_host", f"Host {host!r} is not served; use localhost")
        elif (
            scope["method"] not in SAFE_METHODS
            and origin is not None
            and origin.rstrip("/") not in self.allowed_origins
        ):
            response = _error(
                403, "forbidden_origin", f"Requests from {origin} may not change data"
            )
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)
