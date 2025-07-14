"""Memory Agent — 用户记忆读写（使用 MemoryManager + 自动推断持久化）"""

from __future__ import annotations
import logging

from app.services.agent.agents.base import BaseAgent
from app.services.agent.models import AgentKind, AgentStep
from app.services.agent.memory import MemoryManager

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    """记忆 Agent：三层检索 + 自动推断持久化"""

    @property
    def kind(self) -> AgentKind:
        return AgentKind.MEMORY

    async def _run(self, step: AgentStep) -> AgentStep:
        ctx = step.input or {}
        user_msg = ctx.get("user_message", "")
        mgr = MemoryManager(db=self.db, user_id=self.user_id)

        # 1. 三层检索记忆
        memory_ctx = await mgr.read_context(
            query=user_msg,
            memory_types=["food_preference", "behavior_pattern", "assistant_note"],
        )

        self._track_tool(step, "memory_read_context",
                         {"query_length": len(user_msg)},
                         {"explicit_keys": list(memory_ctx["explicit_preferences"].keys()),
                          "pattern_count": len(memory_ctx["inferred_patterns"])})

        # 2. 如果有最近记录，自动推断 + 持久化
        recent_records = ctx.get("recent_records") or ctx.get("recent_records", [])
        saved_patterns = []
        if recent_records:
            saved_patterns = await mgr.auto_infer_and_save(recent_records)
            self._track_tool(step, "memory_auto_infer",
                             {"record_count": len(recent_records)},
                             {"saved": saved_patterns})

        # 3. 过期清理
        cleaned = await mgr.delete_expired()

        # 4. 读取 settings 中的偏好信息（已有 settings_snapshot）
        settings_snapshot = ctx.get("settings_snapshot", {})
        if settings_snapshot and not memory_ctx["explicit_preferences"]:
            # 从设置中提取偏好注入显式记忆
            avoid_raw = settings_snapshot.get("avoid_foods", "") or ""
            allergen_raw = settings_snapshot.get("allergens", "") or ""
            from app.services.assistant_memory import normalize_preference_text
            memory_ctx["explicit_preferences"]["avoid_foods"] = {
                "list": normalize_preference_text(avoid_raw)
            }
            memory_ctx["explicit_preferences"]["allergens"] = {
                "list": normalize_preference_text(allergen_raw)
            }
            memory_ctx["explicit_preferences"]["taste_preference"] = {
                "value": settings_snapshot.get("taste_preference", "normal")
            }
            memory_ctx["explicit_preferences"]["diet_style"] = {
                "value": settings_snapshot.get("diet_style", "normal")
            }
            memory_ctx["explicit_preferences"]["cuisines"] = {
                "list": settings_snapshot.get("cuisines", [])
            }

        step.complete({
            "memory_context": memory_ctx,
            "saved_patterns": saved_patterns,
            "expired_cleaned": cleaned,
        })
        return step
