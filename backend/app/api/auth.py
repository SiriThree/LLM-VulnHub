from fastapi import APIRouter, Depends, Request, Response

from app.core.config import get_settings
from app.core.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    RequestIdentity,
    authenticate_credentials,
    load_identity,
    require_role,
    revoke_session,
)
from app.schemas.auth import LoginRequest, SessionRead


router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=SessionRead)
def login(payload: LoginRequest, request: Request, response: Response):
    settings = get_settings()
    session = authenticate_credentials(payload.username, payload.password, _client_ip(request))
    response.set_cookie(
        SESSION_COOKIE,
        session.session_key,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        session.csrf_token,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "actor": session.actor, "role": session.role}


@router.get("/status", response_model=SessionRead)
def status(request: Request, response: Response):
    identity = load_identity(request.cookies.get(SESSION_COOKIE), refresh=False)
    response.headers["Cache-Control"] = "no-store"
    if identity is None:
        return {"authenticated": False}
    return {"authenticated": True, "actor": identity.actor, "role": identity.role}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    revoke_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}
