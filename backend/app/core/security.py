from collections.abc import Callable

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings


ROLE_ORDER = {
    "viewer": 1,
    "analyst": 2,
    "admin": 3,
}


class RequestIdentity(BaseModel):
    actor: str
    role: str


def get_request_identity(
    x_actor: str | None = Header(default=None, alias="X-Actor"),
    x_role: str | None = Header(default=None, alias="X-Role"),
) -> RequestIdentity:
    settings = get_settings()
    role = (x_role or settings.default_role).strip().lower()
    actor = (x_actor or settings.default_actor).strip()
    if not actor or len(actor) > 120:
        raise HTTPException(400, "actor must contain 1 to 120 characters")
    if len(role) > 20:
        raise HTTPException(400, "role is too long")
    if role not in ROLE_ORDER:
        raise HTTPException(403, f"unsupported role: {role}")
    return RequestIdentity(actor=actor, role=role)


def require_role(min_role: str) -> Callable[[RequestIdentity], RequestIdentity]:
    if min_role not in ROLE_ORDER:
        raise ValueError(f"unsupported role: {min_role}")

    def dependency(identity: RequestIdentity = Depends(get_request_identity)) -> RequestIdentity:
        if ROLE_ORDER[identity.role] < ROLE_ORDER[min_role]:
            raise HTTPException(403, f"{identity.role} cannot access resource requiring {min_role}")
        return identity

    return dependency
