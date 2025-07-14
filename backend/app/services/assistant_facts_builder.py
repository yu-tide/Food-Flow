"""Unified facts builder — one entry point, delegates to existing specialized builders.

All LLM inputs must go through build_facts_for_llm(). This ensures:
- Chinese-only field names (no internal snake_case keys)
- answer_strategy from reasoning is always included
- No forbidden keys leak into the LLM context
"""
import logging

from app.services.assistant_reasoning_gate import AssistantReasoningResult
from app.services.assistant_llm import (
    build_food_decision_facts_for_llm,
    _build_meal_plan_facts,
    sanitize_llm_context,
)

logger = logging.getLogger(__name__)


def build_facts_for_llm(
    reasoning: AssistantReasoningResult,
    tool_context: dict,
    page_context: dict | None = None,
) -> dict:
    """Build Chinese-only facts dict for the LLM, driven by request_type.

    Delegates to specialized builders for food_decision and meal_plan.
    Uses sanitize_llm_context for generic data-rich paths.
    Returns empty or minimal dict for safe_action/forbidden_action/general_chat.
    """
    rt = reasoning.request_type
    facts: dict = {}

    # ── Food decision: use specialized builder ──
    if rt == "food_decision":
        facts = build_food_decision_facts_for_llm(tool_context)
        logger.warning("TRACE_FACTS_FOR_LLM request_type=%s keys=%s",
                       rt, list(facts.keys()))

    # ── Meal plan: use specialized builder ──
    elif rt == "meal_plan":
        mp = tool_context.get("meal_plan_advice", {})
        facts = _build_meal_plan_facts(mp)
        logger.warning("TRACE_FACTS_FOR_LLM request_type=%s keys=%s",
                       rt, list(facts.keys()))

    # ── Data-rich generic paths: delegate to sanitize_llm_context ──
    elif rt in (
        "dashboard_summary", "weekly_analysis", "settings_advice",
        "record_analysis", "general_chat", "daily_history",
    ):
        if tool_context:
            facts = sanitize_llm_context(tool_context, page_context)
        logger.warning("TRACE_FACTS_FOR_LLM request_type=%s keys=%s",
                       rt, list(facts.keys()))

    # ── Knowledge paths: rag_results passthrough ──
    elif rt in ("nutrition_knowledge", "product_rule"):
        if "rag_results" in tool_context:
            facts["知识库"] = tool_context["rag_results"]
        logger.warning("TRACE_FACTS_FOR_LLM request_type=%s keys=%s has_rag=%s",
                       rt, list(facts.keys()), "rag_results" in tool_context)

    # safe_action, forbidden_action, out_of_scope → facts stay empty (no data needed)
    elif rt == "out_of_scope":
        logger.warning("TRACE_FACTS_FOR_LLM request_type=%s keys=%s (empty — out of scope)", rt, [])

    # ── Always include answer_strategy from reasoning ──
    if reasoning.answer_strategy:
        facts["回答策略"] = reasoning.answer_strategy

    return facts
