"""MemoryManager — 智能体记忆管理器

三层检索策略：
  Tier 1 — 精确偏好匹配（user_explicit 来源）
  Tier 2 — 语义检索（LocalEmbedder，可选）
  Tier 3 — 关键字兜底

自动推断 + 持久化（仅在置信度 >= 0.7 时写入）
记忆合并与过期清理
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent.memory.embeddings import LocalEmbedder

logger = logging.getLogger(__name__)


class MemoryManager:
    """记忆管理器 — 每个用户一个实例"""

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self._embedder = LocalEmbedder()

    # ── 读取 ─────────────────────────────────────────────

    async def read_context(
        self,
        query: str = "",
        memory_types: list[str] | None = None,
        top_k: int = 10,
    ) -> dict:
        """三层检索 → 组装为 LLM-friendly context

        Returns:
            {
                "explicit_preferences": {...},
                "inferred_patterns": [...],
                "top_matches": [...],
                "summary": "简短记忆摘要文本"
            }
        """
        from app.services.assistant_memory import get_user_agent_memories

        types = memory_types or ["food_preference", "behavior_pattern", "assistant_note"]
        memories = await get_user_agent_memories(self.db, self.user_id, types)

        # Tier 1: 分离显式记忆和推断记忆
        explicit = {m["key"]: m["value_json"] for m in memories
                    if m.get("source") == "user_explicit"}
        inferred = [m for m in memories
                    if m.get("source") == "inferred_from_records"]

        # Tier 2: 语义检索（query 非空时）
        top_matches: list[dict] = []
        if query:
            top_matches = self._semantic_search(query, memories, top_k)

        # Tier 3: 关键字兜底（语义检索未返回结果时）
        if not top_matches and query:
            top_matches = self._keyword_fallback(query, memories, top_k)

        # 摘要
        summary_parts = []
        if explicit:
            pref_keys = ", ".join(explicit.keys())
            summary_parts.append(f"显式偏好: {pref_keys}")
        pattern_keys = [p["key"] for p in inferred[:3]]
        if pattern_keys:
            summary_parts.append(f"推断模式: {', '.join(pattern_keys)}")
        if top_matches:
            top_names = [m.get("key", "?") for m in top_matches[:3]]
            summary_parts.append(f"相关记忆: {', '.join(top_names)}")

        return {
            "explicit_preferences": explicit,
            "inferred_patterns": inferred,
            "top_matches": top_matches[:top_k],
            "summary": "; ".join(summary_parts) if summary_parts else "暂无记忆",
        }

    # ── 写入 ─────────────────────────────────────────────

    async def write_memory(
        self,
        key: str,
        value_json: dict,
        memory_type: str = "assistant_note",
        confidence: float = 0.8,
        source: str = "action_result",
        ttl_days: int = 30,
    ) -> dict:
        """写入一条记忆（自动 upsert，不覆盖显式偏好）

        Returns: {"ok": bool, "key": str, "source": str}
        """
        from app.services.assistant_memory import upsert_user_memory

        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days) if ttl_days > 0 else None
        result = await upsert_user_memory(
            self.db, self.user_id, memory_type, key, value_json,
            confidence=confidence, source=source,
            expires_at=expires_at,
        )
        return result or {"ok": False, "note": "写入被拒绝（来源/类型无效或覆盖保护）"}

    # ── 自动推断 ─────────────────────────────────────────

    async def auto_infer_and_save(
        self,
        recent_records: list[dict] | None = None,
        min_confidence: float = 0.7,
    ) -> list[dict]:
        """分析最近记录 → 推断模式 → 高置信度时自动持久化"""
        from app.services.assistant_memory import infer_memory_from_recent_records

        patterns = await infer_memory_from_recent_records(
            self.db, self.user_id, recent_records
        )
        saved = []
        for p in patterns:
            if p.get("confidence", 0) >= min_confidence:
                result = await self.write_memory(
                    key=p["key"],
                    value_json={"level": p.get("level", "notable"),
                                "evidence_count": p.get("evidence_count", 0)},
                    memory_type="behavior_pattern",
                    confidence=p["confidence"],
                    source=p.get("source", "inferred_from_records"),
                    ttl_days=7,  # 推断模式的 TTL 较短
                )
                if result.get("ok"):
                    saved.append(p["key"])

        logger.info("memory auto_infer: %d patterns, %d saved (conf>=%.1f)",
                    len(patterns), len(saved), min_confidence)
        return saved

    # ── 维护 ─────────────────────────────────────────────

    async def delete_expired(self) -> int:
        """清理已过期的记忆条目"""
        from sqlalchemy import delete

        from app.models.assistant_memory import AssistantMemory

        stmt = delete(AssistantMemory).where(
            AssistantMemory.user_id == self.user_id,
            AssistantMemory.expires_at.isnot(None),
            AssistantMemory.expires_at < datetime.now(timezone.utc),
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        deleted = result.rowcount
        if deleted > 0:
            logger.info("memory cleanup: deleted %d expired entries", deleted)
        return deleted

    # ── 内部：语义检索 ──────────────────────────────────

    def _semantic_search(self, query: str, memories: list[dict], top_k: int) -> list[dict]:
        """语义检索（仅当 embedder 可用时）"""
        if not self._embedder.available:
            return []

        q_vec = self._embedder.embed(query)
        if not q_vec:
            return []

        texts = [
            (m, f"{m.get('key', '')} {m.get('value_json', {})}")
            for m in memories
        ]
        scored = []
        for m, txt in texts:
            t_vec = self._embedder.embed(txt[:512])
            if t_vec:
                sim = self._embedder.cosine_similarity(q_vec, t_vec)
                scored.append((sim, m))
        scored.sort(key=lambda x: -x[0])
        return [m for sim, m in scored[:top_k] if sim > 0.3]

    def _keyword_fallback(self, query: str, memories: list[dict], top_k: int) -> list[dict]:
        """关键字排序兜底"""
        return self._embedder.rank_by_keyword(query, memories, text_key="key")[:top_k]
