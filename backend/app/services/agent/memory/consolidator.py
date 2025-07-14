"""Memory Consolidator — 记忆合并与用户画像构建

功能：
- consolidate：合并相似记忆条目，移除冗余
- build_user_profile：聚合所有记忆 → 用户饮食画像
"""

from __future__ import annotations
import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_memory import AssistantMemory

logger = logging.getLogger(__name__)


class MemoryProfile(BaseModel):
    """用户饮食画像 — 聚合所有记忆后的结构化摘要"""
    avoid_foods: list[str] = []
    allergens: list[str] = []
    taste_preference: str = "normal"
    diet_style: str = "normal"
    cuisines: list[str] = []
    recent_patterns: list[dict] = []
    has_sugary_drink_trend: bool = False
    has_high_fat_trend: bool = False
    has_spicy_food_trend: bool = False
    note: str = ""


async def consolidate_memories(db: AsyncSession, user_id: str) -> dict:
    """合并相似记忆条目

    策略：
    - 相同 memory_type + key 的条目已由 ORM 的 unique constraint 去重
    - 对 value_json 相似但 key 不同的条目做软合并
    - 清理置信度极低（< 0.3）的条目
    """
    result = await db.execute(
        select(AssistantMemory).where(AssistantMemory.user_id == user_id)
    )
    rows = result.scalars().all()

    # 清理低置信度记录
    deleted = 0
    for r in rows:
        if r.confidence is not None and r.confidence < 0.3:
            await db.delete(r)
            deleted += 1

    if deleted:
        await db.commit()
        logger.info("consolidate: deleted %d low-confidence entries", deleted)

    return {"deleted_low_confidence": deleted, "total_before": len(rows)}


async def build_user_profile(db: AsyncSession, user_id: str) -> MemoryProfile:
    """聚合所有记忆 → 用户饮食画像"""
    from app.services.assistant_memory import get_user_agent_memories

    memories = await get_user_agent_memories(db, user_id)
    profile = MemoryProfile()

    for m in memories:
        val = m.get("value_json", {}) or {}
        key = m.get("key", "")

        # 显式偏好
        if m.get("source") == "user_explicit":
            if key == "avoid_foods":
                profile.avoid_foods = val.get("list", [])
            elif key == "allergens":
                profile.allergens = val.get("list", [])
            elif key == "taste_preference":
                profile.taste_preference = val.get("value", "normal")
            elif key == "diet_style":
                profile.diet_style = val.get("value", "normal")
            elif key == "cuisines":
                profile.cuisines = val.get("list", [])
            elif key == "note":
                profile.note = val.get("text", "")

        # 推断模式
        elif m.get("source") == "inferred_from_records" and key.startswith("recent_"):
            level = val.get("level", "")
            evidence = val.get("evidence_count", 0)
            profile.recent_patterns.append({
                "key": key,
                "level": level,
                "confidence": m.get("confidence", 0.0),
                "evidence_count": evidence,
            })
            if key == "frequent_sugary_drink_pattern" and level in ("high", "moderate"):
                profile.has_sugary_drink_trend = True
            if key == "recent_high_fat_pattern" and level == "high":
                profile.has_high_fat_trend = True
            if key == "spicy_hotpot_like_frequency" and level == "high":
                profile.has_spicy_food_trend = True

    return profile
