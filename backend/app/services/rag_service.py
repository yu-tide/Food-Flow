"""Simple keyword / ilike RAG search — no embedding, no pgvector."""
import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)


def _score(query: str, title: str, content: str) -> float:
    """Simple keyword match scoring."""
    if not query.strip():
        return 0.0
    keywords = [k.strip().lower() for k in query.split() if k.strip()]
    if not keywords:
        return 0.0

    title_lower = title.lower()
    content_lower = content.lower()
    score = 0.0

    for kw in keywords:
        if kw in title_lower:
            score += 3.0  # title match weight
        if kw in content_lower:
            score += 1.0  # content match weight
    return score


async def search_knowledge(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Search knowledge chunks by keyword, return top matches."""
    if not query or not query.strip():
        return []

    top_k = max(1, min(top_k, 10))

    # Search in chunks first (more granular), fall back to document titles
    keywords = [f"%{k}%" for k in query.strip().split() if k.strip()]
    if not keywords:
        return []

    # Build ilike conditions
    conditions = []
    for kw_pattern in keywords:
        conditions.append(KnowledgeChunk.content.ilike(kw_pattern))

    result = await db.execute(
        select(KnowledgeChunk, KnowledgeDocument.title, KnowledgeDocument.source_type)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(or_(*conditions))
        .limit(top_k * 3)  # fetch extra for scoring
    )
    rows = result.all()

    scored = []
    for chunk, title, source_type in rows:
        s = _score(query, title, chunk.content)
        if s > 0:
            scored.append({
                "title": title,
                "content": chunk.content[:500],
                "score": round(s, 1),
                "source_type": source_type or "nutrition_knowledge",
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


async def search_knowledge_with_confidence(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
) -> dict:
    """Search knowledge with confidence threshold. Wraps search_knowledge().

    Returns:
        {"chunks": [...], "top_score": float, "used": bool, "reason": str}

    Confidence rules (keyword-based):
    - At least one title match (score >= 3.0) → used=True
    - OR 2+ content matches (score >= 1.0) → used=True
    - Otherwise → used=False, no reliable match found
    """
    chunks = await search_knowledge(db, query, top_k)
    top_score = max((c["score"] for c in chunks), default=0.0)

    has_title_match = any(c["score"] >= 3.0 for c in chunks)
    has_multiple_content = sum(1 for c in chunks if c["score"] >= 1.0) >= 2
    used = has_title_match or has_multiple_content

    reason = (
        "命中关键词，检索质量合格"
        if used
        else "检索结果置信不足，知识库中无可靠匹配，不建议硬猜"
    )

    logger.info(
        "rag_service: confidence check top_score=%.1f has_title=%s multi_content=%s used=%s",
        top_score, has_title_match, has_multiple_content, used,
    )

    return {"chunks": chunks, "top_score": top_score, "used": used, "reason": reason}
