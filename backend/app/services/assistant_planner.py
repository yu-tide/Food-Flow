"""Phase 15: Lightweight assistant planner — pure mapper from reasoning to plan.

Does NOT re-call build_reasoning_result(). Takes an already-computed
AssistantReasoningResult and converts it to a structured AssistantPlan.

This is a facade, not a second routing system.
"""
import logging

from pydantic import BaseModel

from app.services.assistant_reasoning_gate import AssistantReasoningResult

logger = logging.getLogger(__name__)


class AssistantPlan(BaseModel):
    intent: str              # same as reasoning.request_type
    steps: list[str]         # derived from required_tools + should_use_rag
    requires_rag: bool       # from reasoning.should_use_rag (NOT hardcoded)
    requires_llm: bool       # false for forbidden/out_of_scope
    response_style: str      # e.g. "personalized_food_decision", "domain_boundary"
    risk_level: str          # none / low / medium / high
    reason: str | None = None


# ── Tool key → readable plan step ──
TOOL_TO_STEP = {
    "dashboard_snapshot": "read_dashboard",
    "weekly_snapshot":    "read_weekly",
    "record_detail":      "read_record_detail",
    "user_settings":      "read_settings",
    "recent_records":     "read_recent_records",
    "food_estimate":      "estimate_food",
    "time_context":       "read_time_context",
    "rag_search":         "search_rag",
}

# ── request_type → response_style ──
RESPONSE_STYLE_MAP = {
    "food_decision":       "personalized_food_decision",
    "meal_plan":           "personalized_meal_plan",
    "record_analysis":     "record_detail",
    "dashboard_summary":   "dashboard_summary",
    "weekly_analysis":     "weekly_summary",
    "daily_history":       "daily_summary",
    "settings_advice":     "settings_goal",
    "nutrition_knowledge": "knowledge_explanation",
    "product_rule":        "product_rule_explanation",
    "safe_action":         "action_confirmation",
    "forbidden_action":    "refusal",
    "out_of_scope":        "domain_boundary",
    "general_chat":        "natural_assistant",
}

# ── request_type → risk_level ──
RISK_LEVEL_MAP = {
    "forbidden_action": "high",
    "safe_action":       "medium",
    "food_decision":     "low",
    "meal_plan":         "low",
    "record_analysis":   "low",
    "dashboard_summary": "low",
    "weekly_analysis":   "low",
    "daily_history":     "low",
    "settings_advice":   "low",
    "nutrition_knowledge": "low",
    "product_rule":       "low",
    "out_of_scope":       "low",
    "general_chat":       "low",
}

# ── Decision modes that skip LLM ──
TEMPLATE_ONLY_MODES = {"refuse_unsafe", "domain_boundary"}


def build_assistant_plan_from_reasoning(
    reasoning: AssistantReasoningResult,
) -> AssistantPlan:
    """Convert an existing reasoning result into a structured plan.

    Does NOT call build_reasoning_result() — reasoning must already be computed.
    """
    rt = reasoning.request_type

    # ── Build steps from required_tools ──
    steps: list[str] = []
    for tool_key in reasoning.required_tools:
        step = TOOL_TO_STEP.get(tool_key)
        if step and step not in steps:
            steps.append(step)

    # RAG step (if triggered but not already covered by required_tools)
    if reasoning.should_use_rag and "search_rag" not in steps:
        steps.append("search_rag")

    # Generate step
    has_data = reasoning.should_use_user_data or reasoning.should_use_rag
    needs_llm = reasoning.decision_mode not in TEMPLATE_ONLY_MODES and not reasoning.should_refuse_or_limit

    if reasoning.should_refuse_or_limit or reasoning.decision_mode in TEMPLATE_ONLY_MODES:
        steps.append("generate_template_answer")
    elif has_data or needs_llm:
        steps.append("generate_llm_answer")
    else:
        steps.append("generate_template_answer")

    # ── response_style ──
    response_style = RESPONSE_STYLE_MAP.get(rt, "natural_assistant")

    # ── risk_level ──
    risk_level = RISK_LEVEL_MAP.get(rt, "low")

    # ── reason ──
    reason = (
        f"decision_mode={reasoning.decision_mode}, "
        f"needs_clarification={reasoning.needs_clarification}, "
        f"should_refuse_or_limit={reasoning.should_refuse_or_limit}"
    )

    plan = AssistantPlan(
        intent=rt,
        steps=steps,
        requires_rag=reasoning.should_use_rag,   # from reasoning, NOT hardcoded
        requires_llm=needs_llm,
        response_style=response_style,
        risk_level=risk_level,
        reason=reason,
    )

    logger.warning(
        "TRACE_ASSISTANT_PLAN_FROM_REASONING request_type=%s decision_mode=%s required_tools=%s",
        rt, reasoning.decision_mode, reasoning.required_tools,
    )

    # Phase 17: Tool registry — validate plan steps don't include disallowed tools
    _validate_plan_steps(plan)

    logger.warning(
        "TRACE_ASSISTANT_PLAN_BUILT intent=%s steps=%s requires_rag=%s requires_llm=%s risk_level=%s",
        plan.intent, plan.steps, plan.requires_rag, plan.requires_llm, plan.risk_level,
    )

    return plan


def _validate_plan_steps(plan: AssistantPlan) -> None:
    """Lightweight: ensure no non-read-only or disabled tool appears in plan steps.

    Only checks steps that map to real tools (via STEP_TO_TOOL).
    Abstract steps (generate_llm_answer, build_safe_action, etc.) are skipped.
    """
    from app.services.tool_registry import STEP_TO_TOOL, get_tool_spec

    disallowed: list[str] = []
    for step in list(plan.steps):
        tool_name = STEP_TO_TOOL.get(step)
        if not tool_name:
            continue  # abstract step, skip
        spec = get_tool_spec(tool_name)
        if not spec or not spec.enabled:
            disallowed.append(f"{step}(not_registered)")
            plan.steps.remove(step)
        elif not spec.read_only:
            disallowed.append(f"{step}(write_tool)")
            plan.steps.remove(step)

    if disallowed:
        logger.warning(
            "TRACE_TOOL_REGISTRY_PLAN_CHECK intent=%s disallowed_tools=%s",
            plan.intent, disallowed,
        )
