from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import DocumentChunk, Vulnerability
from app.schemas.vulnerability import VulnerabilityRead
from app.services.embedding_service import cosine_similarity, embed_text, tokenize
from app.services.llm_service import LLMClient
from app.services.vulnerability_service import serialize_vulnerability


def _keyword_score(query: str, text: str) -> float:
    query_tokens = {token for token in tokenize(query) if len(token) > 1}
    text_tokens = set(tokenize(text))
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = query_tokens & text_tokens
    return len(overlap) / len(query_tokens)


def _search_text(chunk: DocumentChunk) -> str:
    vuln = chunk.vulnerability
    if not vuln:
        return chunk.chunk_text
    return "\n".join(
        [
            vuln.title,
            vuln.vuln_type,
            vuln.severity,
            vuln.affected_component,
            vuln.description,
            vuln.attack_method,
            vuln.impact,
            vuln.mitigation,
            " ".join(tag.name for tag in vuln.tags),
            chunk.chunk_text,
        ]
    )


def search_similar(db: Session, query: str, top_k: int = 5) -> list[dict]:
    q_emb = embed_text(query)
    chunks = db.scalars(
        select(DocumentChunk).options(
            selectinload(DocumentChunk.vulnerability).selectinload(Vulnerability.tags),
        )
    ).all()
    hits = []
    for chunk in chunks:
        if not chunk.vulnerability:
            continue

        search_text = _search_text(chunk)
        vector_score = cosine_similarity(q_emb, chunk.embedding)
        keyword_score = _keyword_score(query, search_text)
        title_score = _keyword_score(query, chunk.vulnerability.title)
        component_score = _keyword_score(query, chunk.vulnerability.affected_component)
        combined = vector_score * 0.55 + keyword_score * 0.3 + title_score * 0.1 + component_score * 0.05

        hits.append(
            {
                "vulnerability": VulnerabilityRead(**serialize_vulnerability(chunk.vulnerability)),
                "similarity": round(combined, 4),
                "chunk_text": chunk.chunk_text,
            }
        )
    return sorted(hits, key=lambda x: x["similarity"], reverse=True)[:top_k]


def _format_hit(index: int, hit: dict) -> str:
    vuln = hit["vulnerability"]
    return "\n".join(
        [
            f"[{index}] 标题：{vuln.title}",
            f"类型：{vuln.vuln_type}",
            f"等级/评分：{vuln.severity} / {vuln.score}",
            f"影响组件：{vuln.affected_component}",
            f"状态：{vuln.status}",
            f"描述：{vuln.description}",
            f"攻击方式：{vuln.attack_method}",
            f"影响：{vuln.impact}",
            f"修复建议：{vuln.mitigation}",
            f"证据片段：{hit['chunk_text'][:1200]}",
        ]
    )


async def ask(db: Session, question: str, top_k: int = 5) -> dict:
    hits = search_similar(db, question, top_k)
    usable_hits = [hit for hit in hits if hit["similarity"] >= 0.08] or hits[: min(3, len(hits))]

    if not usable_hits:
        return {
            "answer": "当前漏洞库里没有足够相关的记录来回答这个问题。建议先补充相关漏洞条目，或换成更具体的问题，例如包含组件名、漏洞类型或攻击方式。",
            "references": [],
        }

    context = "\n\n".join(_format_hit(index, hit) for index, hit in enumerate(usable_hits, start=1))
    prompt = f"""用户问题：{question}

可用漏洞库记录：
{context}

请用中文回答，并遵守：
1. 只基于“可用漏洞库记录”回答，不要编造库里没有的信息。
2. 如果问题是防护/缓解类，按“主要风险、可执行措施、排查重点”组织。
3. 如果问题是对比/归纳类，先给结论，再列共同点和差异。
4. 每个关键结论后用 [1]、[2] 这样的编号标注参考记录。
5. 如果证据不足，要明确说明哪些部分无法从当前记录确认。
6. 最后给出“参考记录”小节，列出引用过的标题。"""
    answer = await LLMClient().chat_text(
        "你是 LLM-VulnHub 的 RAG 安全问答助手。你必须忠实使用检索上下文，回答清晰、具体、可复核；资料不足时要明确说明不足。",
        prompt,
    )
    titles = "\n".join(f"- [{index}] {hit['vulnerability'].title}" for index, hit in enumerate(usable_hits, start=1))
    if "参考记录" not in answer:
        answer = f"{answer.rstrip()}\n\n参考记录：\n{titles}"
    return {"answer": answer, "references": usable_hits}
