from fastapi import APIRouter, Depends

from app.core.security import RequestIdentity, require_role
from app.schemas.security_model import SecurityModelRead
from app.services.security_model_service import get_security_model

router = APIRouter(prefix="/security-model", tags=["security-model"])


@router.get("", response_model=SecurityModelRead)
def read_security_model(
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    return get_security_model()
