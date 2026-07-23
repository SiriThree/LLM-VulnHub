from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, require_role
from app.db.session import get_db
from app.schemas.rag import RagAskRequest, RagAskResponse, RagSearchRequest, SearchHit
from app.services.rag_service import ask, record_rag_audit, search_similar

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=list[SearchHit])
def search_api(
    payload: RagSearchRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    hits = search_similar(db, payload.query, payload.top_k, role=identity.role)
    record_rag_audit(
        db,
        actor=identity.actor,
        role=identity.role,
        action="search",
        query=payload.query,
        top_k=payload.top_k,
        hits=hits,
    )
    return hits


@router.post("/ask", response_model=RagAskResponse)
async def ask_api(
    payload: RagAskRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    return await ask(db, payload.question, payload.top_k, actor=identity.actor, role=identity.role)
