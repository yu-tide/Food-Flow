"""memory_tool — 用户记忆读写工具

原始依赖：assistant_memory
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

from app.services.agent.tools.registry import ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)


@ToolRegistry.register(ToolSpec(
    name="memory_read",
    description="读取用户的长期记忆（饮食偏好、行为模式、过敏信息）",
    risk_level="none",
    requires_context=["db", "user_id"],
    timeout_seconds=10,
    categories=["memory"],
))
async def memory_read(
    db,
    user_id: str,
    memory_types: list[str] | None = None,
) -> dict:
    """读取用户记忆"""
    from app.services.assistant_memory import get_user_agent_memories

    if memory_types is None:
        memory_types = ["food_preference", "behavior_pattern", "assistant_note"]

    memories = await get_user_agent_memories(db, user_id, memory_types)
    return {
        "count": len(memories),
        "explicit": [m for m in memories if m.get("source") == "user_explicit"],
        "inferred": [m for m in memories if m.get("source") == "inferred_from_records"],
    }


@ToolRegistry.register(ToolSpec(
    name="memory_write",
    description="写入一条用户记忆（自动 upsert，不会覆盖用户显式设置）",
    risk_level="low",
    requires_context=["db", "user_id"],
    requires_confirmation=False,
    timeout_seconds=10,
    categories=["memory"],
))
async def memory_write(
    db,
    user_id: str,
    key: str,
    value_json: dict,
    memory_type: str = "assistant_note",
    confidence: float = 0.8,
    source: str = "action_result",
) -> dict:
    """写入记忆"""
    from app.services.assistant_memory import upsert_user_memory

    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    result = await upsert_user_memory(
        db, user_id, memory_type, key, value_json,
        confidence=confidence, source=source,
        expires_at=expires_at,
    )
    return result or {"ok": False, "note": "写入被拒绝（可能是不允许的类型或来源）"}


@ToolRegistry.register(ToolSpec(
    name="memory_infer",
    description="根据最近记录自动推断用户行为模式（高辣频率、高脂模式、含糖饮品）",
    risk_level="none",
    requires_context=["db", "user_id"],
    timeout_seconds=10,
    categories=["memory"],
))
async def memory_infer(
    db,
    user_id: str,
    recent_records: list[dict] | None = None,
) -> list[dict]:
    """行为模式推断"""
    from app.services.assistant_memory import infer_memory_from_recent_records

    return await infer_memory_from_recent_records(db, user_id, recent_records)
