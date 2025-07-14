"""Hybrid Intent Classifier — 关键词规则 + LLM 兜底"""

from __future__ import annotations
import logging

from app.services.agent.models import IntentResult
from app.services.assistant_reasoning_gate import (
    build_reasoning_result,
)

logger = logging.getLogger(__name__)


class HybridIntentClassifier:
    """混合意图分类器

    策略：
    Phase 1 — 关键词规则引擎（O(1)，确定性的）
    Phase 2 — 规则引擎不确定时，走 LLM 兜底
    """

    def __init__(self, mode: str = "hybrid"):
        self.mode = mode  # "rules_only" | "hybrid" | "llm_only"

    async def classify(
        self,
        message: str,
        page: str = "",
        page_context: dict | None = None,
    ) -> IntentResult:
        msg = message.strip()
        ctx = page_context or {}

        # Phase 1: 关键词规则引擎
        rule_result = build_reasoning_result(msg, page, ctx)
        rt = rule_result.request_type

        # 对于规则引擎明确分类的意图，直接使用（不回退到 LLM）
        if rt not in ("general_chat", "out_of_scope") or self.mode == "rules_only":
            return IntentResult(
                intent=rt,
                confidence=0.95,
                requires_user_data=rule_result.should_use_user_data,
                requires_rag=rule_result.should_use_rag,
                risk_level=rule_result.risk_level or "low",
                needs_clarification=rule_result.needs_clarification,
                clarification_question=(
                    "你想查看哪条记录？请在记录列表中点击一条具体记录后再问我，"
                    "我可以帮你分析成分、热量和保存状态。"
                    if rt in ("forbidden_action", "safe_action", "record_analysis")
                    and rule_result.needs_clarification
                    else ""
                ),
                entities=[],
                raw_plan_summary=rule_result.answer_strategy,
            )

        # Phase 2: 规则引擎不确定时，LLM 兜底
        if self.mode in ("hybrid", "llm_only"):
            return await self._llm_classify(msg, page, ctx)

        # Pure rules_only mode: 保留原始结果
        return IntentResult(
            intent=rt,
            confidence=0.7,
            requires_user_data=rule_result.should_use_user_data,
            requires_rag=rule_result.should_use_rag,
        )

    async def _llm_classify(self, message: str, page: str, ctx: dict) -> IntentResult:
        """LLM-based intent classification fallback"""
        from app.core.config import settings

        if settings.AI_MODE == "mock":
            return _mock_classify(message, page)

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.BAILIAN_API_KEY,
                base_url=settings.BAILIAN_BASE_URL,
            )

            prompt = f"""你是 FoodFlow 的意图分类器。判断用户消息属于哪种意图。

可选的意图类型：
- food_decision: 用户想吃/喝某个食物，问能不能吃、合不合适
- meal_plan: 用户要求推荐餐食、制定饮食计划
- record_analysis: 用户问某条记录的详情、成分、热量
- dashboard_summary: 用户问今天吃了多少、今日摄入
- weekly_analysis: 用户问本周数据、周统计
- daily_history: 用户问某天(昨天/前天/指定日期)的数据
- settings_advice: 用户问目标设置、营养目标
- nutrition_knowledge: 用户问营养知识(原理/区别/作用)
- safe_action: 用户要求执行保存/确认等操作
- general_chat: 打招呼或仅文字问候
- out_of_scope: 与饮食营养完全无关的话题

当前页面: {page}
用户消息: {message}

只返回意图名称，不要其他内容。
"""
            resp = client.chat.completions.create(
                model=settings.BAILIAN_MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=10,
            )
            intent = (resp.choices[0].message.content or "").strip().lower()
            # 验证意图
            valid_intents = {
                "food_decision", "meal_plan", "record_analysis",
                "dashboard_summary", "weekly_analysis", "daily_history",
                "settings_advice", "nutrition_knowledge", "safe_action",
                "general_chat", "out_of_scope",
            }
            if intent not in valid_intents:
                intent = "general_chat"

            return IntentResult(intent=intent, confidence=0.85)

        except Exception as e:
            logger.warning("LLM classify fallback failed: %s", e)
            return IntentResult(intent="general_chat", confidence=0.5)


def _mock_classify(message: str, page: str) -> IntentResult:
    """Mock 模式 — 简单规则"""
    msg = message.lower()

    if any(kw in msg for kw in ("你好", "hi", "hello", "在吗")):
        return IntentResult(intent="general_chat", confidence=0.95)

    if any(kw in msg for kw in ("能吃", "能喝", "可以吃", "适不适合", "推荐")):
        return IntentResult(intent="food_decision", confidence=0.9, requires_user_data=True)

    if any(kw in msg for kw in ("本周", "这周", "周统计")):
        return IntentResult(intent="weekly_analysis", confidence=0.9, requires_user_data=True)

    if any(kw in msg for kw in ("今天", "今日")):
        return IntentResult(intent="dashboard_summary", confidence=0.9, requires_user_data=True)

    if any(kw in msg for kw in ("昨天", "前天", "记录")):
        return IntentResult(intent="daily_history", confidence=0.8, requires_user_data=True)

    if any(kw in msg for kw in ("目标", "设置")):
        return IntentResult(intent="settings_advice", confidence=0.85, requires_user_data=True)

    if any(kw in msg for kw in ("保存", "确认")):
        return IntentResult(intent="safe_action", confidence=0.9)

    return IntentResult(intent="general_chat", confidence=0.7)
