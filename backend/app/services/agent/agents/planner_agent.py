"""Planner Agent — 将意图转化为可执行的步骤 DAG"""

from __future__ import annotations
import logging
import uuid

from app.services.agent.agents.base import BaseAgent
from app.services.agent.models import (
    AgentKind, AgentStep, ExecutionPlan, IntentResult, StepStatus,
)

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """规划器：接收 IntentResult 生成 ExecutionPlan"""

    @property
    def kind(self) -> AgentKind:
        return AgentKind.PLANNER

    async def create_plan(self, intent: IntentResult, user_context: dict) -> ExecutionPlan:
        """根据意图类型生成对应的执行步骤"""
        intent_map = self._build_intent_map()
        plan_fn = intent_map.get(intent.intent, self._plan_fallback)
        return await plan_fn(intent, user_context)

    async def replan(self, current: ExecutionPlan, feedback: str) -> ExecutionPlan:
        """收到反思反馈后重新规划剩余步骤"""
        logger.warning("TRACE_REPLAN iteration=%d feedback=%s",
                       current.current_iteration, feedback[:80])
        current.current_iteration += 1

        for step in current.steps:
            if step.status in (StepStatus.FAILED, StepStatus.SKIPPED):
                step.status = StepStatus.PENDING
                step.output = None
                step.error_message = None
        return current

    # ── Intent → Plan 映射 ──────────────────────────────────

    def _build_intent_map(self, ) -> dict:
        return {
            "food_decision":       self._plan_food_decision,
            "meal_plan":           self._plan_meal_plan,
            "record_analysis":     self._plan_record_analysis,
            "dashboard_summary":   self._plan_dashboard_summary,
            "weekly_analysis":     self._plan_weekly_analysis,
            "daily_history":       self._plan_daily_history,
            "settings_advice":     self._plan_settings_advice,
            "nutrition_knowledge": self._plan_nutrition_knowledge,
            "safe_action":         self._plan_safe_action,
            "general_chat":        self._plan_general_chat,
        }

    async def _plan_food_decision(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="food_decision", steps=[
            AgentStep(id=_uid(), agent=AgentKind.MEMORY,     description="读取用户记忆与偏好"),
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER,   description="获取今日摄入 + 剩余热量"),
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER,   description="估算目标食物营养"),
            AgentStep(id=_uid(), agent=AgentKind.REFLECTOR,  description="反思营养数据一致性"),
            AgentStep(id=_uid(), agent=AgentKind.PLANNER,    description="综合判断并生成建议"),
        ], context=ctx, max_iterations=2)

    async def _plan_meal_plan(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="meal_plan", steps=[
            AgentStep(id=_uid(), agent=AgentKind.MEMORY,    description="读取饮食偏好与目标"),
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER,  description="获取今日摄入 + 剩余预算"),
            AgentStep(id=_uid(), agent=AgentKind.PLANNER,   description="生成个性化餐食推荐"),
        ], context=ctx)

    async def _plan_record_analysis(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="record_analysis", steps=[
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER,  description="获取记录详情"),
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER,  description="分析营养成分与问题"),
        ], context=ctx)

    async def _plan_dashboard_summary(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="dashboard_summary", steps=[
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER, description="获取今日仪表盘数据"),
        ], context=ctx)

    async def _plan_weekly_analysis(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="weekly_analysis", steps=[
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER, description="获取本周统计数据"),
            AgentStep(id=_uid(), agent=AgentKind.REFLECTOR, description="校验数据完整性"),
        ], context=ctx)

    async def _plan_daily_history(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="daily_history", steps=[
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER, description="查询指定日期记录"),
        ], context=ctx)

    async def _plan_settings_advice(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="settings_advice", steps=[
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER, description="获取当前用户设置"),
        ], context=ctx)

    async def _plan_nutrition_knowledge(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="nutrition_knowledge", steps=[
            AgentStep(id=_uid(), agent=AgentKind.ANALYZER, description="搜索知识库"),
        ], context=ctx)

    async def _plan_safe_action(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="safe_action", steps=[
            AgentStep(id=_uid(), agent=AgentKind.VALIDATOR, description="校验操作权限"),
            AgentStep(id=_uid(), agent=AgentKind.PLANNER,   description="执行安全操作"),
        ], context=ctx)

    async def _plan_fallback(self, intent: IntentResult, ctx: dict) -> ExecutionPlan:
        return ExecutionPlan(intent="general_chat", steps=[
            AgentStep(id=_uid(), agent=AgentKind.PLANNER, description="通用回复"),
        ], context=ctx)


def _uid() -> str:
    return uuid.uuid4().hex[:8]
