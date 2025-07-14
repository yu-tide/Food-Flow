"""knowledge_tool — RAG 知识检索工具

原始依赖：rag_service
"""

from __future__ import annotations
import logging

from app.services.agent.tools.registry import ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)


@ToolRegistry.register(ToolSpec(
    name="knowledge_search",
    description="搜索营养知识库（RAG），返回相关文档片段",
    risk_level="none",
    requires_context=["db"],
    timeout_seconds=10,
    categories=["knowledge"],
))
async def knowledge_search(
    db,
    query: str,
    top_k: int = 3,
) -> list[dict]:
    """知识库搜索"""
    from app.services.rag_service import search_knowledge_with_confidence

    result = await search_knowledge_with_confidence(db, query, top_k=top_k)

    if result.get("used"):
        return [
            {"title": c["title"], "content": c["content"],
             "score": c.get("score", 0.0), "source": c.get("source", "")}
            for c in result.get("chunks", [])
        ]
    return []


@ToolRegistry.register(ToolSpec(
    name="knowledge_categories",
    description="获取知识库中可用的分类列表",
    risk_level="none",
    requires_context=["db"],
    timeout_seconds=5,
    categories=["knowledge"],
))
async def knowledge_categories(db) -> list[str]:
    """知识库分类"""
    from app.services.rag_service import search_knowledge
    # 使用高频关键词作为分类提示
    return [
        "nutrition_basics", "diet_knowledge", "food_analysis",
        "product_rules", "common_sense",
    ]
