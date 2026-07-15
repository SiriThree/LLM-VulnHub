from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import DocumentChunk, Vulnerability
from app.db.session import SessionLocal
from app.services.embedding_service import embed_texts
from app.services.vulnerability_service import build_vulnerability_chunk_text


def rebuild_embeddings(batch_size: int = 32) -> int:
    db = SessionLocal()
    try:
        vulnerabilities = list(db.scalars(select(Vulnerability).order_by(Vulnerability.id)))
        updated = 0
        for offset in range(0, len(vulnerabilities), batch_size):
            batch = vulnerabilities[offset : offset + batch_size]
            texts = [build_vulnerability_chunk_text(vulnerability) for vulnerability in batch]
            embeddings = embed_texts(texts)
            for vulnerability, text, embedding in zip(batch, texts, embeddings):
                chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.vulnerability_id == vulnerability.id))
                if chunk is None:
                    chunk = DocumentChunk(vulnerability_id=vulnerability.id, chunk_text=text, embedding=embedding)
                    db.add(chunk)
                else:
                    chunk.chunk_text = text
                    chunk.embedding = embedding
                updated += 1
            db.commit()
            print(f"Reindexed {updated}/{len(vulnerabilities)} vulnerabilities")
        return updated
    finally:
        db.close()


if __name__ == "__main__":
    settings = get_settings()
    total = rebuild_embeddings()
    print(f"Embedding rebuild complete: model={settings.embedding_model}, dim={settings.embedding_dim}, total={total}")
