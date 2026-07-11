from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.rag import RagAskRequest, RagAskResponse, RagSearchRequest, SearchHit
from app.services.rag_service import ask, search_similar

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=list[SearchHit])
def search_api(payload: RagSearchRequest, db: Session = Depends(get_db)):
    return search_similar(db, payload.query, payload.top_k)


@router.post("/ask", response_model=RagAskResponse)
async def ask_api(payload: RagAskRequest, db: Session = Depends(get_db)):
    return await ask(db, payload.question, payload.top_k)
