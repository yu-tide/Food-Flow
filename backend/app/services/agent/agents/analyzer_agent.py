"""Analyzer Agent — 数据查询与分析执行器"""

from __future__ import annotations
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent.agents.base import BaseAgent
from app.services.agent.models import AgentKind, AgentStep
from app.services.assistant_tools import (
    get_dashboard_snapshot, get_weekly_snapshot, get_daily_snapshot,
    get_record_detail_snapshot, get_settings_snapshot,
    search_recent_confirmed,
)

logger = logging.getLogger(__name__)


class AnalyzerAgent(BaseAgent):
    """分析器：实际执行业务数据查询"""

    @property
    def kind(self) -> AgentKind:
        return AgentKind.ANALYZER

    async def _run(self, step: AgentStep) -> AgentStep:
        desc = step.description
        ctx = step.input or {}

        if "今日摄入" in desc or "仪表盘" in desc:
            data = await get_dashboard_snapshot(self.db, self.user_id)
            self._track_tool(step, "get_dashboard_snapshot", {}, data)
            step.complete({"dashboard_summary": data})

        elif "本周统计" in desc:
            data = await get_weekly_snapshot(self.db, self.user_id)
            self._track_tool(step, "get_weekly_snapshot", {}, data)
            step.complete({"weekly_summary": data})

        elif "指定日期" in desc or "每日历史" in desc:
            target_date = ctx.get("target_date", "")
            tz = ctx.get("timezone", "Asia/Shanghai")
            label = ctx.get("date_label", target_date)
            data = await get_daily_snapshot(self.db, self.user_id, target_date, tz, label)
            self._track_tool(step, "get_daily_snapshot", {"date": target_date}, data)
            step.complete({"daily_snapshot": data})

        elif "记录详情" in desc:
            record_id = ctx.get("record_id", "")
            data = await get_record_detail_snapshot(self.db, self.user_id, record_id)
            self._track_tool(step, "get_record_detail_snapshot", {"record_id": record_id}, data)
            step.complete({"record_detail": data})

        elif "用户设置" in desc:
            data = await get_settings_snapshot(self.db, self.user_id)
            self._track_tool(step, "get_settings_snapshot", {}, data)
            step.complete({"user_settings": data})

        elif "估算" in desc or "营养" in desc:
            food_name = ctx.get("food_name", "")
            data = await self._estimate_food(food_name, ctx)
            step.complete({"food_estimate": data})

        elif "知识库" in desc:
            query = ctx.get("query", "")
            rag_results = await self._search_rag(query)
            self._track_tool(step, "search_knowledge", {"query": query}, rag_results)
            step.complete({"rag_results": rag_results})

        elif "最近记录" in desc or "最近饮食" in desc:
            limit = ctx.get("limit", 5)
            data = await search_recent_confirmed(self.db, self.user_id, limit)
            self._track_tool(step, "search_recent_confirmed", {"limit": limit}, data)
            step.complete({"recent_records": data})

        else:
            logger.warning("analyzer: unknown description=%s", desc)
            step.complete({"note": f"未匹配到查询: {desc}"})

        return step

    async def _estimate_food(self, food_name: str, ctx: dict) -> dict:
        """估算食物营养 — 复用现有 nutrition_estimator"""
        from app.schemas.ai_food import RecognizedFoodItem
        from app.services.nutrition_estimator import estimate_nutrition

        weight_g = ctx.get("weight_g", 200.0)
        item = RecognizedFoodItem(
            food_name=food_name, estimated_weight_g=weight_g, source="agent",
        )
        result = estimate_nutrition(item)
        return {
            "food_name": food_name,
            "calories": result.calories,
            "protein": result.protein,
            "carbs": result.carbs,
            "fat": result.fat,
            "confidence": result.confidence,
            "source": result.source,
        }

    async def _search_rag(self, query: str) -> list[dict]:
        """搜索知识库 — 复用现有 rag_service"""
        from app.services.rag_service import search_knowledge
        results = await search_knowledge(self.db, query, top_k=3)
        return [
            {"title": r["title"], "content": r["content"], "score": r.get("score", 0.0)}
            for r in results
        ]
