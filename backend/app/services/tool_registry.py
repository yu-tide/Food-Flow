"""Phase 17: Tool Registry — 轻量工具注册中心.

Describes all assistant-available tools. Provides lookup, listing, and
lightweight allow/deny checks. Does NOT replace business-level auth.
"""
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict = {}
    output_schema: dict = {}
    read_only: bool
    requires_confirmation: bool
    risk_level: str  # "none" | "low" | "medium" | "high"
    enabled: bool = True


# ── Step → tool name mapping (only steps backed by real tools) ──
STEP_TO_TOOL: dict[str, str] = {
    "read_dashboard":       "get_dashboard_snapshot",
    "read_weekly":          "get_weekly_snapshot",
    "read_record_detail":   "get_record_detail_snapshot",
    "read_settings":        "get_settings_snapshot",
    "read_recent_records":  "search_recent_confirmed",
    "search_rag":           "search_knowledge",
    "estimate_food":        "estimate_food_for_decision",
    "build_food_decision":  "build_food_decision_context",
    "read_daily_snapshot":  "get_daily_snapshot",
    "read_memory_context":  "build_memory_context_for_food_decision",
}
# Abstract steps NOT in STEP_TO_TOOL (not backed by real tools):
#   generate_llm_answer, generate_template_answer, build_safe_action,
#   domain_boundary_response, refuse_forbidden_action

# ── Registered tools ──
TOOLS: dict[str, ToolSpec] = {
    "get_dashboard_snapshot": ToolSpec(
        name="get_dashboard_snapshot",
        description="获取今日已保存记录的营养汇总（热量、蛋白质、碳水、脂肪、目标、剩余热量）",
        input_schema={},
        output_schema={"consumed_calories": "int", "target_calories": "int", "remaining_calories": "int"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "get_daily_snapshot": ToolSpec(
        name="get_daily_snapshot",
        description="获取用户指定日期的已保存饮食记录营养汇总（支持昨天/前天/指定日期），按本地时区查询",
        input_schema={"target_date": "str", "timezone_str": "str", "date_label": "str"},
        output_schema={"date": "str", "record_count": "int", "total_calories": "int", "protein": "int", "carbs": "int", "fat": "int"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "get_weekly_snapshot": ToolSpec(
        name="get_weekly_snapshot",
        description="获取本周已保存记录的每日营养统计和总览",
        input_schema={},
        output_schema={"week_start": "str", "week_end": "str", "daily": "list", "avg_daily_calories": "int"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "get_record_detail_snapshot": ToolSpec(
        name="get_record_detail_snapshot",
        description="获取单条记录的详细成分、营养估算和保存状态",
        input_schema={"record_id": "str"},
        output_schema={"name": "str", "calories": "int", "is_confirmed": "bool", "components": "list"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "get_settings_snapshot": ToolSpec(
        name="get_settings_snapshot",
        description="获取用户营养目标和偏好设置（热量目标、目标类型、忌口、过敏信息等）",
        input_schema={},
        output_schema={"target_calories": "int", "goal_type": "str", "avoid_foods": "str"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "search_recent_confirmed": ToolSpec(
        name="search_recent_confirmed",
        description="查询最近已保存的饮食记录，用于趋势分析和个性化建议",
        input_schema={"limit": "int"},
        output_schema={"list[dict]": "每条包含 name, calories, protein, carbs, fat, meal_type, created_at"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "search_knowledge": ToolSpec(
        name="search_knowledge",
        description="从 FoodFlow 垂直领域知识库中检索饮食、营养、产品规则相关内容",
        input_schema={"query": "str", "top_k": "int"},
        output_schema={"list[dict]": "每条包含 title, content, score, source_type"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "estimate_food_for_decision": ToolSpec(
        name="estimate_food_for_decision",
        description="根据食物/饮品名称估算营养数据（热量、宏量营养、风险标签、建议选择等）",
        input_schema={"food_name": "str"},
        output_schema={"typical": "int", "min": "int", "max": "int", "risk_tags": "list[str]"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "build_food_decision_context": ToolSpec(
        name="build_food_decision_context",
        description="综合 dashboard、settings、recent records 和食物估算，计算个性化饮食决策建议级别",
        input_schema={"dashboard_summary": "dict", "settings": "dict", "recent_records": "list", "food_estimate": "dict"},
        output_schema={"recommendation_level": "str", "consumed_calories": "int", "remaining_calories": "int"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "build_memory_context_for_food_decision": ToolSpec(
        name="build_memory_context_for_food_decision",
        description="读取用户显式偏好和已保存记录推断的行为模式，生成个性化记忆上下文",
        input_schema={"settings_snapshot": "dict", "recent_records": "list"},
        output_schema={"explicit_preferences": "dict", "inferred_patterns": "list"},
        read_only=True, requires_confirmation=False, risk_level="none",
    ),
    "execute_assistant_action": ToolSpec(
        name="execute_assistant_action",
        description="执行用户确认的安全操作（保存记录、打开详情/设置、生成周报）。仅限用户在前端点击确认后调用。",
        input_schema={"action_id": "str", "type": "str", "payload": "dict"},
        output_schema={"ok": "bool", "message": "str", "result": "dict"},
        read_only=False, requires_confirmation=True, risk_level="medium",
    ),
}


# ── Public API ──

def get_tool_spec(name: str) -> ToolSpec | None:
    """Get a tool's metadata by name."""
    return TOOLS.get(name)


def list_enabled_tools() -> list[ToolSpec]:
    """List all enabled tools."""
    return [t for t in TOOLS.values() if t.enabled]


def is_tool_allowed(name: str, context: dict | None = None) -> bool:
    """Check if a tool is allowed to execute given the current context.

    Rules:
    1. Unknown or disabled tool → False
    2. read_only=True → True (always allowed for reading)
    3. requires_confirmation=True → only if context.confirmed_by_user is True
    4. risk_level=high → False (explicitly blocked in first version)
    """
    ctx = context or {}
    tool = TOOLS.get(name)
    if not tool:
        logger.warning("TRACE_TOOL_REGISTRY_UNKNOWN_TOOL name=%s", name)
        return False
    if not tool.enabled:
        logger.warning("TRACE_TOOL_REGISTRY_DISABLED_TOOL name=%s", name)
        return False

    if tool.read_only:
        return True

    if tool.risk_level == "high":
        logger.warning("TRACE_TOOL_REGISTRY_HIGH_RISK_BLOCKED name=%s", name)
        return False

    if tool.requires_confirmation:
        allowed = ctx.get("confirmed_by_user") is True
        logger.warning(
            "TRACE_TOOL_REGISTRY_ACTION_CHECK action_type=%s allowed=%s confirmed_by_user=%s source=%s",
            ctx.get("action_type", "?"), allowed,
            ctx.get("confirmed_by_user"), ctx.get("source", "unknown"),
        )
        return allowed

    return False
