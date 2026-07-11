from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import DocumentChunk
from app.schemas.vulnerability import VulnerabilityRead
from app.services.embedding_service import cosine_similarity, embed_text
from app.services.llm_service import LLMClient
from app.services.vulnerability_service import serialize_vulnerability


def search_similar(db: Session, query: str, top_k: int = 5) -> list[dict]:
    q_emb = embed_text(query)
    chunks = db.scalars(select(DocumentChunk).options(selectinload(DocumentChunk.vulnerability))).all()
    hits = []
    for chunk in chunks:
        if not chunk.vulnerability:
            continue
        sim = cosine_similarity(q_emb, chunk.embedding)
        hits.append({"vulnerability": VulnerabilityRead(**serialize_vulnerability(chunk.vulnerability)), "similarity": round(sim, 4), "chunk_text": chunk.chunk_text})
    return sorted(hits, key=lambda x: x["similarity"], reverse=True)[:top_k]


async def ask(db: Session, question: str, top_k: int = 5) -> dict:
    hits = search_similar(db, question, top_k)
    context = "\n\n".join([f"标题：{h['vulnerability'].title}\n类型：{h['vulnerability'].vuln_type}\n描述：{h['chunk_text']}" for h in hits])
    prompt = f"用户问题：{question}\n\n漏洞库上下文：\n{context}"
    answer = await LLMClient().chat_text("你是一个 AI 大模型漏洞库问答助手。回答必须基于上下文，最后说明参考记录。", prompt)
    if hits:
        titles = "、".join(h["vulnerability"].title for h in hits[:3])
        answer = f"{answer}\n\n参考漏洞：{titles}"
    return {"answer": answer, "references": hits}
