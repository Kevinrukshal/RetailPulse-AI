"""Single-operator local API access; not a multi-user authorization system."""

import secrets
import time
from collections import OrderedDict, deque
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param
from starlette.responses import JSONResponse

from app.core.config import get_settings

bearer = HTTPBearer(auto_error=False)
# Bound both request frequency and the number of remembered source addresses.
_request_windows = OrderedDict()
_rate_lock = Lock()


def enforce_rate_limit(request: Request) -> None:
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _rate_lock:
        window = _request_windows.pop(address, deque())
        while window and window[0] <= now - 60:
            window.popleft()
        _request_windows[address] = window
        if len(_request_windows) > 1024:
            _request_windows.popitem(last=False)
        if len(window) >= 120:
            raise HTTPException(429, "Too many requests", headers={"Retry-After": "60"})
        window.append(now)


def require_access_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    if getattr(request.state, "access_checked", False):
        return
    enforce_rate_limit(request)
    configured = get_settings().api_access_token
    expected = configured.get_secret_value() if configured else ""
    if len(expected) < 32:
        raise HTTPException(503, "API access is not configured")
    if not credentials or not secrets.compare_digest(
        credentials.credentials.encode(), expected.encode()
    ):
        raise HTTPException(
            401, "A valid access token is required", headers={"WWW-Authenticate": "Bearer"}
        )


class APIAccessMiddleware:
    """Authenticate before framework body parsing; bound buffered JSON requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or not scope["path"].startswith("/api/")
            or scope["method"] == "OPTIONS"
        ):
            return await self.app(scope, receive, send)
        request = Request(scope)
        scheme, value = get_authorization_scheme_param(request.headers.get("authorization"))
        credentials = (
            HTTPAuthorizationCredentials(scheme=scheme, credentials=value)
            if scheme.lower() == "bearer" and value
            else None
        )
        try:
            require_access_token(request, credentials)
        except HTTPException as exc:
            response = JSONResponse(
                {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
            )
            return await response(scope, receive, send)
        request.state.access_checked = True
        # Uploads stream and enforce their own byte cap inside the authenticated route.
        if scope["path"].rstrip("/") == "/api/v1/assistant/query":
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > 16 * 1024:
                    response = JSONResponse(
                        {"detail": "Request body is too large"}, status_code=413
                    )
                    return await response(scope, receive, send)
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
            sent = False

            async def bounded_receive():
                nonlocal sent
                if sent:
                    return await receive()
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            return await self.app(scope, bounded_receive, send)
        return await self.app(scope, receive, send)
