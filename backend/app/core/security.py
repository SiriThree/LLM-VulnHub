from collections.abc import Callable
import hashlib
import json
import secrets
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings


ROLE_ORDER = {
    "guest": 0,
    "viewer": 1,
    "analyst": 2,
    "admin": 3,
}
ROLE_VISIBILITIES = {
    "guest": ("public",),
    "viewer": ("public",),
    "analyst": ("public", "internal"),
    "admin": ("public", "internal", "restricted"),
}
SESSION_COOKIE = "llm_vulnhub_session"
CSRF_COOKIE = "llm_vulnhub_csrf"
PUBLIC_AUTH_PATHS = {
    "/api/v1/auth/guest",
    "/api/v1/auth/login",
    "/api/v1/auth/status",
}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PROTECTED_RESPONSE_HEADERS = {
    "cache-control": "no-store, max-age=0",
    "pragma": "no-cache",
    "x-content-type-options": "nosniff",
}


class RequestIdentity(BaseModel):
    actor: str
    role: str
    session_key: str
    csrf_token: str


def allowed_visibilities(role: str) -> tuple[str, ...]:
    return ROLE_VISIBILITIES.get(role, ())


def can_access_visibility(role: str, visibility: str) -> bool:
    return visibility in allowed_visibilities(role)


def _session_key(raw_token: str) -> str:
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return f"auth:session:{digest}"


def _login_attempt_key(client_ip: str, username: str) -> str:
    subject = hashlib.sha256(f"{client_ip}:{username.lower()}".encode("utf-8")).hexdigest()
    return f"auth:login-attempt:{subject}"


def _redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _redis_call(method: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(_redis(), method)(*args, **kwargs)
    except RedisError as exc:
        raise HTTPException(503, "authentication service is unavailable") from exc


def _configured_accounts() -> dict[str, tuple[str, str]]:
    settings = get_settings()
    configured = {
        "admin": (settings.auth_admin_password, "admin"),
        "analyst": (settings.auth_analyst_password, "analyst"),
        "viewer": (settings.auth_viewer_password, "viewer"),
    }
    accounts: dict[str, tuple[str, str]] = {}
    for username, (secret_value, role) in configured.items():
        if secret_value is None:
            continue
        password = secret_value.get_secret_value()
        if len(password) < 12:
            continue
        accounts[username] = (password, role)
    return accounts


def issue_session(actor: str, role: str) -> RequestIdentity:
    if role not in ROLE_ORDER or not actor or len(actor) > 120:
        raise ValueError("invalid session identity")
    settings = get_settings()
    raw_session = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    identity = RequestIdentity(
        actor=actor,
        role=role,
        session_key=_session_key(raw_session),
        csrf_token=csrf_token,
    )
    payload = json.dumps(
        {
            "actor": identity.actor,
            "role": identity.role,
            "csrf_token": identity.csrf_token,
        },
        separators=(",", ":"),
    )
    _redis_call("set", identity.session_key, payload, ex=settings.auth_session_ttl_seconds)
    return identity.model_copy(update={"session_key": raw_session})


def authenticate_credentials(username: str, password: str, client_ip: str) -> RequestIdentity:
    settings = get_settings()
    username = username.strip().lower()
    if not username or len(username) > 120 or len(password) > 256:
        raise HTTPException(401, "invalid username or password")

    accounts = _configured_accounts()
    if not accounts:
        raise HTTPException(503, "no authentication accounts are configured")

    attempt_key = _login_attempt_key(client_ip, username)
    attempts = int(_redis_call("get", attempt_key) or 0)
    if attempts >= settings.auth_login_max_attempts:
        raise HTTPException(429, "too many login attempts; try again later")

    account = accounts.get(username)
    valid = bool(account) and secrets.compare_digest(password, account[0])
    if not valid:
        next_attempts = int(_redis_call("incr", attempt_key))
        if next_attempts == 1:
            _redis_call("expire", attempt_key, settings.auth_login_window_seconds)
        raise HTTPException(401, "invalid username or password")

    _redis_call("delete", attempt_key)
    return issue_session(username, account[1])


def load_identity(raw_session: str | None, *, refresh: bool = True) -> RequestIdentity | None:
    if not raw_session or len(raw_session) > 256:
        return None
    redis_key = _session_key(raw_session)
    payload = _redis_call("get", redis_key)
    if not payload:
        return None
    try:
        data = json.loads(payload)
        actor = str(data["actor"])
        role = str(data["role"])
        csrf_token = str(data["csrf_token"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        _redis_call("delete", redis_key)
        return None
    if role not in ROLE_ORDER or not actor or len(actor) > 120 or not csrf_token:
        _redis_call("delete", redis_key)
        return None
    if refresh:
        _redis_call("expire", redis_key, get_settings().auth_session_ttl_seconds)
    return RequestIdentity(actor=actor, role=role, session_key=redis_key, csrf_token=csrf_token)


def revoke_session(raw_session: str | None) -> None:
    if raw_session and len(raw_session) <= 256:
        _redis_call("delete", _session_key(raw_session))


def get_request_identity(request: Request) -> RequestIdentity:
    identity = getattr(request.state, "identity", None)
    if not isinstance(identity, RequestIdentity):
        raise HTTPException(401, "authentication required")
    return identity


def require_role(min_role: str) -> Callable[[RequestIdentity], RequestIdentity]:
    if min_role not in ROLE_ORDER:
        raise ValueError(f"unsupported role: {min_role}")

    def dependency(identity: RequestIdentity = Depends(get_request_identity)) -> RequestIdentity:
        if ROLE_ORDER[identity.role] < ROLE_ORDER[min_role]:
            raise HTTPException(403, f"{identity.role} cannot access resource requiring {min_role}")
        return identity

    return dependency


class AuthenticationMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = scope.get("path", "")
        if not path.startswith("/api/v1") or path in PUBLIC_AUTH_PATHS or request.method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        try:
            identity = load_identity(request.cookies.get(SESSION_COOKIE))
        except HTTPException as exc:
            await JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
                headers=PROTECTED_RESPONSE_HEADERS,
            )(scope, receive, send)
            return
        if identity is None:
            await JSONResponse(
                {"detail": "authentication required"},
                status_code=401,
                headers=PROTECTED_RESPONSE_HEADERS,
            )(scope, receive, send)
            return

        if request.method in MUTATING_METHODS:
            cookie_token = request.cookies.get(CSRF_COOKIE, "")
            header_token = request.headers.get("x-csrf-token", "")
            if not cookie_token or not header_token:
                await JSONResponse(
                    {"detail": "CSRF token required"},
                    status_code=403,
                    headers=PROTECTED_RESPONSE_HEADERS,
                )(scope, receive, send)
                return
            if not secrets.compare_digest(cookie_token, identity.csrf_token) or not secrets.compare_digest(header_token, identity.csrf_token):
                await JSONResponse(
                    {"detail": "invalid CSRF token"},
                    status_code=403,
                    headers=PROTECTED_RESPONSE_HEADERS,
                )(scope, receive, send)
                return

        scope.setdefault("state", {})["identity"] = identity

        async def send_with_security_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in PROTECTED_RESPONSE_HEADERS.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
