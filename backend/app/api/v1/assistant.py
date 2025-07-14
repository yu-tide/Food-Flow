"""FoodFlow AI Assistant — Phase 11: streaming + shared context builder."""
import asyncio
import json
import logging
import uuid

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.assistant_decision import build_food_decision_context
from app.services.assistant_food_estimator import estimate_food_for_decision
from app.schemas.assistant_actions import (
    AssistantActionExecuteRequest,
    AssistantActionExecuteResponse,
)
from app.services.assistant_actions import build_suggested_actions, execute_assistant_action
from app.services.assistant_llm import (
    generate_assistant_answer,
    generate_assistant_answer_stream,
)
from app.services.assistant_reasoning_gate import build_reasoning_result
from app.services.assistant_tools import (
    get_daily_snapshot,
    get_dashboard_snapshot,
    get_record_detail_snapshot,
    get_settings_snapshot,
    get_weekly_snapshot,
    search_recent_confirmed,
)
from app.services.rag_service import search_knowledge, search_knowledge_with_confidence

router = APIRouter(prefix="/assistant", tags=["AI 助手"])


class ChatRequest(BaseModel):
    message: str
    page: str = ""
    page_context: dict = {}
    session_id: str | None = None
    history: list[dict] = []


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[dict] = []
    suggested_actions: list[dict] = []


GREETINGS = {"你好", "hi", "hello", "在吗", "你是谁", "你能做什么", "你能干什么", "你会什么"}
RECORD_KEYWORDS = {"这顿饭", "这条记录", "这个记录", "当前记录", "热量为什么", "脂肪是否偏高", "成分", "校准", "重量", "调整成分"}
RECENT_KEYWORDS = {"最近", "哪几顿", "高热量", "高脂肪", "脂肪偏高", "蛋白质最高", "热量最高"}
WEEKLY_KEYWORDS = {"本周", "这周", "周统计", "蛋白质达标", "这一周", "这周哪天"}
TODAY_KEYWORDS = {"今天", "今日", "今天吃得", "今日摄入", "今天摄入", "今天吃了"}
SETTINGS_KEYWORDS = {"目标", "热量目标", "蛋白质目标", "怎么设置目标"}
KNOWLEDGE_KEYWORDS = {
    "怎么吃", "原理", "区别", "减脂", "增肌",
    "冒菜", "麻辣烫", "火锅", "未保存记录", "统计规则",
}

# Keywords that should SKIP RAG even if they also match KNOWLEDGE_KEYWORDS
DATA_INTENT_KEYWORDS = {
    "今天", "今日", "本周", "这周", "最近", "记录",
    "这顿饭", "当前记录", "热量", "蛋白质达标", "热量最高",
}
FOOD_NAMES = {"冒菜", "麻辣烫", "火锅", "炸鸡", "奶茶", "烧烤", "汉堡", "披萨", "面条", "米饭", "盖饭", "沙拉", "甜品", "零食"}
FOOD_DECISION_KEYWORDS = {
    "可以吃吗", "能吃吗", "适合吗", "怎么样", "会不会超标", "要不要吃",
    "吃多少", "点什么", "怎么点", "推荐吗", "中午吃", "晚上吃", "今天吃",
    "现在吃", "能喝吗", "喝奶茶", "吃这个", "吃顿",
    "可以吃", "能吃", "能喝", "可以喝", "能不能吃", "能不能喝",
    "想吃", "想喝", "该不该吃", "该不该喝",
}
MEAL_PLAN_KEYWORDS = {
    "夜宵方案", "制定夜宵", "夜宵推荐", "夜宵吃什么",
    "晚餐方案", "晚餐推荐", "早餐方案", "早餐推荐", "午餐方案", "午餐推荐",
    "今天吃什么", "今天吃点什么", "推荐吃点什么", "帮我安排一餐",
    "减脂夜宵", "低脂夜宵", "清淡夜宵",
    "帮我制定", "饮食方案", "一餐建议",
    "夜宵", "方案",
}
VAGUE_KEYWORDS = {"这个怎么看", "这里怎么回事", "帮我分析", "这个正常吗", "怎么看", "什么意思", "怎么办"}

PAGE_FALLBACKS = {
    "/dashboard": "你正在查看首页仪表盘。可以问我「今天摄入多少」「本周蛋白质达标了吗」「最近哪几顿热量最高」等问题。",
    "/records": "你正在查看饮食记录列表。可以问我「最近哪几顿热量最高」「本周统计」等问题，或点击某条记录后问「这顿饭的热量为什么这么高」。",
    "/confirm": "你正在校准识别结果。可以问我「这条记录的成分怎么调整」「菜名候选是什么意思」「如何校准成分重量」等问题。",
    "/statistics": "你正在查看每周统计。可以问我「本周蛋白质达标了吗」「这周哪天热量最高」「帮我总结这周饮食」等问题。",
    "/settings": "你正在设置页面。可以问我「怎么设置适合我的目标」「蛋白质目标怎么计算」「AI 分析偏好是什么意思」等问题。",
    "/upload": "你正在上传餐图。可以问我「上传什么样的图片识别更准」「如何让 AI 更准确分析」等问题。",
}

GENERAL_INTRO = "我是 FoodFlow AI 助手，可以帮你查看饮食记录、营养目标、每周统计和分析结果。试着问我「今日热量」「本周蛋白质」「最近哪几顿热量最高」等问题。"


def _match_any(msg: str, keywords: set[str]) -> bool:
    return any(kw in msg for kw in keywords)


def _page_fallback(page: str) -> str:
    for prefix, reply in PAGE_FALLBACKS.items():
        if page.startswith(prefix):
            return reply
    return GENERAL_INTRO


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_context_result(
    msg: str, page: str, ctx: dict, tool_context: dict,
    sources: list, answer: str, reasoning,
    force_empty_actions: bool = False,
    plan: object = None,
) -> dict:
    """Build the standard context dict returned by build_assistant_context."""
    if force_empty_actions or reasoning.should_refuse_or_limit:
        actions = []
    else:
        actions = [a.model_dump() for a in build_suggested_actions(msg, page, ctx, tool_context)]

    result = {
        "user_message": msg,
        "page": page,
        "page_context": ctx,
        "tool_context": tool_context,
        "sources": sources,
        "template_fallback": answer,
        "suggested_actions": actions,
        "reasoning": reasoning,
        "response_style": {
            "mode": "concise_product_assistant",
            "max_words": 180,
            "format": "conclusion_reasons_next_step",
            "avoid": ["raw_internal_status", "long_paragraph", "markdown_table", "tool_json"],
        },
    }
    if plan is not None:
        result["plan"] = plan.model_dump()
    return result


def _parse_local_time(ctx: dict) -> tuple[int | None, int | None]:
    """Robustly parse local_hour (0-23) and local_minute (0-59) from page_context."""
    hour = None
    minute = None
    try:
        h = int(ctx.get("local_hour", ""))
        if 0 <= h <= 23:
            hour = h
    except (ValueError, TypeError):
        pass
    try:
        m = int(ctx.get("local_minute", ""))
        if 0 <= m <= 59:
            minute = m
    except (ValueError, TypeError):
        pass
    return hour, minute


def _parse_daily_date(ctx: dict, msg: str) -> tuple[str, str]:
    """Parse a target date and human-readable label from the user's message.

    Uses page_context.timezone to compute "yesterday"/"前天" relative to user's local date.
    Dates like "5月17日" are parsed directly.
    Returns (target_date_iso, date_label).
    """
    import re
    from datetime import date, datetime, timedelta
    from zoneinfo import ZoneInfo

    tz_str = ctx.get("timezone", "Asia/Shanghai")
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")

    # Use client_time_iso if available, otherwise server local time
    client_iso = ctx.get("client_time_iso", "")
    try:
        local_now = datetime.fromisoformat(client_iso).astimezone(tz)
    except (ValueError, TypeError):
        local_now = datetime.now(tz)

    today = local_now.date()

    if "昨天" in msg:
        target = today - timedelta(days=1)
        return (target.isoformat(), "昨天")
    if "前天" in msg:
        target = today - timedelta(days=2)
        return (target.isoformat(), "前天")
    if "大前天" in msg:
        target = today - timedelta(days=3)
        return (target.isoformat(), "大前天")

    # "上周X"
    weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    m = re.search(r"上周([一二三四五六日天])", msg)
    if m:
        target_wd = weekday_map.get(m.group(1), 0)
        days_back = (today.weekday() - target_wd) % 7 + 7
        target = today - timedelta(days=days_back)
        return (target.isoformat(), f"上周{m.group(1)}")

    # "星期X" (this week)
    m2 = re.search(r"星期([一二三四五六日天])", msg)
    if m2:
        target_wd = weekday_map.get(m2.group(1), 0)
        days_back = (today.weekday() - target_wd) % 7
        target = today - timedelta(days=days_back)
        return (target.isoformat(), f"星期{m2.group(1)}")

    # "X月X日" / "X月X号" / bare "X月X" — parse with current year
    m3 = re.search(r"(\d{1,2})月(\d{1,2})(?:[日号])?", msg)
    if m3:
        month, day = int(m3.group(1)), int(m3.group(2))
        try:
            target = date(today.year, month, day)
        except ValueError:
            target = today
        return (target.isoformat(), f"{month}月{day}日")

    # "2026-05-16" format
    m4 = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", msg)
    if m4:
        try:
            target = date(int(m4.group(1)), int(m4.group(2)), int(m4.group(3)))
        except ValueError:
            target = today
        return (target.isoformat(), f"{m4.group(2)}月{m4.group(3)}日")

    # "5-16" or "5.16" format (month-day)
    m5 = re.search(r"(\d{1,2})[-.](\d{1,2})", msg)
    if m5:
        month, day = int(m5.group(1)), int(m5.group(2))
        try:
            target = date(today.year, month, day)
        except ValueError:
            target = today
        return (target.isoformat(), f"{month}月{day}日")

    # Fallback: yesterday (safe default for daily queries)
    target = today - timedelta(days=1)
    return (target.isoformat(), "昨天")


async def _maybe_rag(db, msg: str) -> tuple[list, list]:
    results = await search_knowledge(db, msg, top_k=3)
    rag_results = []
    rag_sources = []
    for r in results:
        rag_results.append({"title": r["title"], "content": r["content"]})
        rag_sources.append({"type": "knowledge", "title": r["title"]})
    return rag_results, rag_sources


async def build_assistant_context(
    db: AsyncSession,
    body: ChatRequest,
    user_id: str,
) -> dict:
    """Shared context builder — now dispatched by reasoning gate, not raw keyword chain."""
    msg = body.message
    page = body.page or ""
    ctx = body.page_context or {}
    record_id = ctx.get("record_id", "")
    answer = ""
    tool_context: dict = {}
    sources: list[dict[str, str]] = []

    # ═══ NEW: Reasoning gate classifies intent BEFORE any data fetching ═══
    reasoning = build_reasoning_result(msg, page, ctx)
    logger.warning("TRACE_REASONING_RESULT request_type=%s decision_mode=%s required_tools=%s risk_level=%s",
                   reasoning.request_type, reasoning.decision_mode,
                   reasoning.required_tools, reasoning.risk_level)

    # ═══ Phase 15: Convert reasoning to structured plan (pure mapper, no re-classification) ═══
    from app.services.assistant_planner import build_assistant_plan_from_reasoning
    plan = build_assistant_plan_from_reasoning(reasoning)
    logger.warning("TRACE_ASSISTANT_PLAN_USED intent=%s", plan.intent)

    # ═══ Pre-data check: needs clarification (e.g. record_analysis without record_id) ═══
    if reasoning.needs_clarification:
        answer = "你想查看哪条记录？请在记录列表中点击一条具体记录后再问我，我可以帮你分析成分、热量和保存状态。"
        sources.append({"type": "assistant_info", "title": "需要更多信息"})
        return _build_context_result(msg, page, ctx, {}, sources, answer, reasoning, plan=plan)

    # ═══ Pre-data check: refuse unsafe actions immediately ═══
    if reasoning.should_refuse_or_limit:
        answer = (
            "抱歉，我目前不支持自动删除或修改数据。如果需要删除记录，请在记录列表中手动操作。"
            "如果需要调整营养目标，可以前往「设置」页面修改。"
        )
        sources.append({"type": "assistant_info", "title": "操作受限"})
        return _build_context_result(msg, page, ctx, {}, sources, answer, reasoning, force_empty_actions=True, plan=plan)

    # ═══ Dispatch by reasoning.request_type ═══

    # ── Food decision ──
    if reasoning.request_type == "food_decision":
        logger.warning("ENTER_FOOD_DECISION_BRANCH")
        food_name = next((f for f in FOOD_NAMES if f in msg), "")
        dash = await get_dashboard_snapshot(db, user_id)
        logger.warning("DASHBOARD_SNAPSHOT_FOR_ASSISTANT raw consumed=%s target=%s remaining=%s record_count=%s",
                       dash.get('consumed_calories'), dash.get('target_calories'), dash.get('remaining_calories'), dash.get('record_count'))
        logger.warning("TRACE_DASHBOARD_FACTS consumed=%s target=%s remaining=%s record_count=%s",
                       dash.get('consumed_calories'), dash.get('target_calories'), dash.get('remaining_calories'), dash.get('record_count'))
        s = await get_settings_snapshot(db, user_id)
        recent = await search_recent_confirmed(db, user_id, limit=3)
        estimate = estimate_food_for_decision(food_name)
        decision = build_food_decision_context(dash, s, recent, estimate, ctx)

        tool_context = {
            "personalized_food_decision": {
                "food_name": food_name,
                "food_estimate": estimate,
                "decision": decision,
                "today": dash,
                "recent_records": recent,
            }
        }
        sources = [
            {"type": "dashboard_summary", "title": "今日摄入"},
            {"type": "user_settings", "title": "营养目标"},
            {"type": "recent_records", "title": "最近饮食记录"},
        ]

        # Phase 16: Build memory context (transient inference, no auto-write)
        from app.services.assistant_memory import build_memory_context_for_food_decision
        memory_ctx = await build_memory_context_for_food_decision(db, user_id, s, recent)
        if memory_ctx:
            tool_context["memory_context"] = memory_ctx

        level = decision["recommendation_level"]
        consumed = decision["consumed_calories"]
        target = decision["target_calories"]
        rem = decision["remaining_calories"]
        typical = decision["estimated_calories"] or 0
        min_c = decision.get("estimated_min") or 0
        max_c = decision.get("estimated_max") or 0
        after = decision["remaining_after_eating"]
        time_ctx = decision.get("time_context", {})
        is_late = time_ctx.get("is_late_night", False)
        time_stmt = time_ctx.get("current_time_statement", "")
        meal_stmt = time_ctx.get("current_meal_statement", "")

        record_note = ""
        if dash["record_count"] == 0:
            record_note = " 注意：根据已保存记录，你今天目前是 0 kcal。如果你有正在处理或未保存的餐图，它还没有计入统计，保存后判断会更准确。"

        better = estimate.get("better_choices", [])
        avoid = estimate.get("avoid_choices", [])
        better_str = "、".join(better[:4]) if better else ""
        avoid_str = "、".join(avoid[:4]) if avoid else ""

        if level == "yes":
            answer = f"可以吃，今天热量预算充足。根据已保存记录，你今天已摄入 {consumed} kcal，目标 {target} kcal，剩余约 {rem} kcal。{food_name}一份通常约 {typical} kcal（{min_c}-{max_c} kcal），吃完预计还剩约 {after} kcal。建议正常吃，优先选清淡做法。{record_note}"
        elif level == "yes_but_control":
            if is_late:
                answer = f"从热量看可以，但{meal_stmt}不太建议吃正常份量的{food_name}。根据已保存记录，你今天已摄入 {consumed} kcal，目标 {target} kcal，热量预算还充足。{food_name}一份通常约 {typical} kcal，偏油/偏高热量。如果确实想吃，建议只吃小份。"
            else:
                answer = f"可以吃，但建议控制份量。根据已保存记录，你今天已摄入 {consumed} kcal，目标 {target} kcal，剩余约 {rem} kcal。{food_name}一份通常约 {typical} kcal（{min_c}-{max_c} kcal），偏油/偏高热量。建议小份、少油。"
            if better_str:
                answer += f" 推荐选择：{better_str}。"
            if avoid_str:
                answer += f" 尽量避开：{avoid_str}。"
            answer += record_note
        elif level == "small_portion_only":
            if is_late:
                answer = f"不太建议现在吃正常份量的{food_name}。{time_stmt}根据已保存记录，你今天还剩余约 {rem} kcal，普通一份约 {typical} kcal。{meal_stmt}如果确实想吃，建议只吃小份。"
            else:
                answer = f"可以吃一点，但不建议正常份量。根据已保存记录，你今天已摄入 {consumed} kcal，目标 {target} kcal，剩余约 {rem} kcal。{food_name}普通一份约 {typical} kcal，正常吃可能接近或超过目标。建议小份或半份。"
            if better_str:
                answer += f" 推荐：{better_str}。"
            answer += record_note
        else:
            if is_late:
                answer = f"不太建议现在吃{food_name}。{time_stmt}根据已保存记录，你今天剩余约 {rem} kcal，普通一份约 {typical} kcal。{meal_stmt}如果一定要吃，建议只吃很小份，选清淡做法。更稳妥的选择是清淡蛋白质加蔬菜。{record_note}"
            else:
                answer = f"今天不太建议吃正常份量的{food_name}。根据已保存记录，你今天已摄入 {consumed} kcal，目标 {target} kcal，剩余约 {rem} kcal。普通一份约 {typical} kcal，吃完大概率超过目标。建议小份或选清淡替代方案。{record_note}"

    # ── Meal plan ──
    elif reasoning.request_type == "meal_plan":
        logger.warning("ENTER_MEAL_PLAN_BRANCH")
        dash = await get_dashboard_snapshot(db, user_id)
        logger.warning("MEAL_PLAN_DASHBOARD consumed=%s target=%s remaining=%s record_count=%s",
                       dash.get('consumed_calories'), dash.get('target_calories'),
                       dash.get('remaining_calories'), dash.get('record_count'))
        s = await get_settings_snapshot(db, user_id)
        recent = await search_recent_confirmed(db, user_id, limit=3)

        from app.services.assistant_decision import build_meal_time_context
        time_ctx = build_meal_time_context(ctx) if ctx else {}

        consumed = dash.get("consumed_calories") or 0
        if dash.get("record_count", 0) == 0:
            consumed = 0
        target = dash.get("target_calories") or s.get("target_calories") or 2000
        remaining = max(target - consumed, 0)

        meal_decision = {
            "consumed_calories": consumed,
            "target_calories": target,
            "remaining_calories": remaining,
            "record_count": dash.get("record_count", 0),
        }

        period = time_ctx.get("meal_period", "general")
        task_map = {
            "late_night": "给用户制定夜宵建议，优先低脂、清淡、小份、好消化的食物。",
            "midnight": "给用户制定夜宵建议，这个时间应该建议非常清淡、极小份的食物。",
            "breakfast": "给用户制定早餐建议，优先营养均衡、易消化的食物。",
            "lunch": "给用户制定午餐建议，可以按正餐安排。",
            "afternoon": "给用户制定下午加餐建议，建议控制份量。",
            "dinner": "给用户制定晚餐建议，注意不要太油。",
        }

        tool_context = {
            "meal_plan_advice": {
                "task": task_map.get(period, "给用户制定饮食建议"),
                "time_context": time_ctx,
                "decision": meal_decision,
                "meal_period": period,
                "recent_records": recent,
            }
        }
        sources = [
            {"type": "dashboard_summary", "title": "今日摄入"},
            {"type": "user_settings", "title": "营养目标"},
            {"type": "recent_records", "title": "最近饮食记录"},
        ]

        # Phase 16: Build memory context (transient inference, no auto-write)
        from app.services.assistant_memory import build_memory_context_for_food_decision
        memory_ctx = await build_memory_context_for_food_decision(db, user_id, s, recent)
        if memory_ctx:
            tool_context["memory_context"] = memory_ctx

        record_note = ""
        if dash["record_count"] == 0:
            record_note = " 注意：根据已保存记录，你今天目前是 0 kcal。如果有正在处理或未保存的餐图，它还没有计入统计，保存后我再帮你调整建议。"

        time_stmt = time_ctx.get("current_time_statement", "")
        meal_stmt = time_ctx.get("current_meal_statement", "")

        answer = f"{time_stmt}{meal_stmt}根据已保存记录，你今天已摄入 {consumed} kcal，目标 {target} kcal，剩余 {remaining} kcal。{record_note}"

    # ── Record analysis (has record_id, passed needs_clarification check above) ──
    elif reasoning.request_type == "record_analysis":
        detail = await get_record_detail_snapshot(db, user_id, record_id)
        if detail:
            tool_context = {"food_record": detail}
            is_confirm = page.startswith("/confirm/")
            status_note = "" if detail["is_confirmed"] else "（注意：该记录尚未保存，不会进入统计。）"
            comp_list = [c["name"] for c in detail["components"][:6] if c.get("name")]
            comp_str = "、".join(comp_list) if comp_list else "暂未获取到成分"
            answer = (
                f"当前{'待确认' if is_confirm else ''}记录：{detail['name']}，{detail['weight']}，约 {detail['calories']} kcal。"
                f"蛋白质 {detail['protein']}g · 碳水 {detail['carbs']}g · 脂肪 {detail['fat']}g。"
                f"包含 {detail['component_count']} 项成分：{comp_str}。{status_note}"
            )
            sources.append({"type": "food_record", "title": f"{detail['name']} · {detail['calories']} kcal", "id": record_id})
        else:
            answer = "未找到该记录，请确认记录是否存在或是否属于当前账号。"

    # ── Weekly analysis ──
    elif reasoning.request_type == "weekly_analysis":
        week = await get_weekly_snapshot(db, user_id)
        tool_context = {"weekly_statistics": week}
        if week["record_count"] > 0:
            lines = [
                f"本周（{week['week_start']} 至 {week['week_end']}）共 {week['record_count']} 条已保存记录。",
                f"平均每日 {week['avg_daily_calories']} kcal，总热量 {week['total_calories']} kcal。",
                f"蛋白质合计 {week['total_protein']}g · 碳水 {week['total_carbs']}g · 脂肪 {week['total_fat']}g。",
            ]
            daily_str = " · ".join(f"{d['day']} {d['calories']}kcal" for d in week["daily"])
            lines.append(f"每日热量：{daily_str}")
            answer = "\n".join(lines)
        else:
            answer = "本周还没有已保存的饮食记录。上传餐图并保存后即可查看统计。"
        sources.append({"type": "weekly_statistics", "title": "本周饮食统计"})

    # ── Daily history (昨天/前天/specific date) ──
    elif reasoning.request_type == "daily_history":
        logger.warning("TRACE_DAILY_QUERY_DETECTED")
        target_date, date_label = _parse_daily_date(ctx, msg)
        logger.warning("TRACE_DAILY_DATE_RANGE target_date=%s date_label=%s", target_date, date_label)

        tz = ctx.get("timezone", "Asia/Shanghai")
        dash = await get_daily_snapshot(db, user_id, target_date, tz, date_label)
        s = await get_settings_snapshot(db, user_id)
        tool_context = {"daily_snapshot": dash, "user_settings": s}

        target = s.get("target_calories") or dash.get("target_calories") or 2000

        if dash.get("record_count", 0) > 0:
            answer = (
                f"{date_label}：已摄入 {dash.get('total_calories', 0)} kcal，目标 {target} kcal。"
                f"蛋白质 {dash.get('protein', 0)}g · 碳水 {dash.get('carbs', 0)}g · 脂肪 {dash.get('fat', 0)}g。"
                f"共 {dash.get('record_count', 0)} 条已保存记录。"
            )
        else:
            answer = (
                f"{date_label}没有已保存饮食记录，所以我这里统计到的摄入是 0 kcal。"
                "正在分析或未保存的记录不会计入统计。"
            )
        sources.append({"type": "daily_snapshot", "title": f"{date_label}饮食汇总"})

    # ── Dashboard summary ──
    elif reasoning.request_type == "dashboard_summary":
        dash = await get_dashboard_snapshot(db, user_id)
        tool_context = {"dashboard_summary": dash}
        if dash["record_count"] > 0:
            answer = (
                f"今日已摄入 {dash['consumed_calories']} kcal，目标 {dash['target_calories']} kcal，"
                f"剩余 {dash['remaining_calories']} kcal。"
                f"蛋白质 {dash['protein']}g · 碳水 {dash['carbs']}g · 脂肪 {dash['fat']}g。"
                f"共 {dash['record_count']} 条记录。"
            )
        else:
            answer = "今天还没有已保存的饮食记录。上传餐图并保存后即可查看今日统计。"
        sources.append({"type": "dashboard_summary", "title": "今日饮食汇总"})

    # ── Settings advice ──
    elif reasoning.request_type == "settings_advice":
        s = await get_settings_snapshot(db, user_id)
        tool_context = {"user_settings": s}
        goal_labels = {"maintain": "维持体重", "lose": "减脂", "gain": "增肌"}
        mode_labels = {"agent_recommended": "系统推荐", "manual": "手动设置"}
        answer = (
            f"当前营养目标：每日 {s['target_calories']} kcal，"
            f"蛋白质 {s['target_protein'] or '未设置'}g，"
            f"碳水 {s['target_carbs'] or '未设置'}g，"
            f"脂肪 {s['target_fat'] or '未设置'}g。"
            f"目标类型：{goal_labels.get(s['goal_type'], s['goal_type'])}，"
            f"目标来源：{mode_labels.get(s['nutrition_goal_mode'], s['nutrition_goal_mode'])}。"
        )
        sources.append({"type": "user_settings", "title": "营养目标设置"})

    # ── Out of scope: polite refusal, no data, no RAG ──
    elif reasoning.request_type == "out_of_scope":
        answer = ("我主要负责 FoodFlow 里的饮食记录、营养分析、餐食建议和产品规则。"
                  "这个问题和饮食管理关系不大，我就不展开了。"
                  "你可以问我：今天还能吃什么、这周蛋白质达标了吗、或者怎么调整饮食目标。")
        sources.append({"type": "assistant_info", "title": "服务范围"})

    # ── General chat (greetings, recent records, vague, fallback) ──
    elif reasoning.request_type == "general_chat":
        if msg.strip() in GREETINGS or len(msg) <= 3:
            answer = GENERAL_INTRO
            sources.append({"type": "assistant_info", "title": "FoodFlow AI 助手"})
        elif "recent_records" in reasoning.required_tools:
            recent = await search_recent_confirmed(db, user_id, limit=5)
            tool_context = {"recent_records": recent}
            if recent:
                total = sum(r["calories"] for r in recent)
                max_item = max(recent, key=lambda r: r["calories"])
                lines = [f"最近 {len(recent)} 条已保存记录，合计 {total} kcal。"]
                lines.append(f"其中热量最高的是 {max_item['name']}，{max_item['calories']} kcal。")
                lines.append("详细：")
                for r in recent:
                    lines.append(f"· {r['name']} {r['calories']}kcal P{r['protein']}g C{r['carbs']}g F{r['fat']}g")
                answer = "\n".join(lines)
                sources.append({"type": "recent_records", "title": f"最近 {len(recent)} 条记录"})
            else:
                answer = "还没有已保存的饮食记录。上传餐图并保存后即可查看。"
        elif _match_any(msg, VAGUE_KEYWORDS):
            answer = _page_fallback(page)
            sources.append({"type": "assistant_info", "title": "页面帮助"})
        else:
            answer = _page_fallback(page)
            sources.append({"type": "assistant_info", "title": "FoodFlow AI 助手"})

    # ── Safe action, nutrition_knowledge, product_rule: page-aware fallback ──
    else:
        answer = _page_fallback(page)
        sources.append({"type": "assistant_info", "title": "FoodFlow AI 助手"})

    # ═══ RAG enrichment — driven by reasoning.should_use_rag ═══
    if reasoning.should_use_rag:
        logger.warning("TRACE_RAG_DECISION should_use_rag=%s reason=%s",
                       reasoning.should_use_rag, reasoning.request_type)
        logger.warning("TRACE_RAG_SEARCH_START query=%s", msg[:80])
        rag_result = await search_knowledge_with_confidence(db, msg, top_k=3)
        logger.warning("TRACE_RAG_SEARCH_END count=%s top_score=%s used=%s",
                       len(rag_result["chunks"]), rag_result["top_score"], rag_result["used"])
        if rag_result["used"]:
            chunks = rag_result["chunks"]
            rag_data = []
            rag_srcs = []
            for r in chunks:
                rag_data.append({"title": r["title"], "content": r["content"]})
                rag_srcs.append({"type": "knowledge", "title": r["title"]})
            tool_context["rag_results"] = rag_data
            sources.extend(rag_srcs)
        else:
            # Low confidence: tell LLM not to guess
            tool_context["rag_note"] = "知识库检索结果置信不足，无可靠匹配。请告知用户当前知识库里没有足够可靠的信息，不建议硬猜。"
            logger.warning("TRACE_RAG_LOW_CONFIDENCE reason=%s", rag_result["reason"])

    return _build_context_result(msg, page, ctx, tool_context, sources, answer, reasoning, plan=plan)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.warning("ENTER_NORMAL_CHAT message=%s page=%s", body.message[:80], body.page)
    logger.warning("TRACE_PAGE_CONTEXT raw_page_context=%s", json.dumps(body.page_context, ensure_ascii=False))
    logger.warning("TRACE_PAGE_CONTEXT_TIME raw_local_hour=%s raw_local_minute=%s local_time_text=%s timezone=%s",
                   body.page_context.get('local_hour'),
                   body.page_context.get('local_minute'),
                   body.page_context.get('local_time_text'),
                   body.page_context.get('timezone'))
    ctx = await build_assistant_context(db, body, str(current_user.id))
    logger.warning("TRACE_ASSISTANT_INTENT intent=%s", [s.get('type','?') for s in ctx.get('sources',[])])
    llm_answer = generate_assistant_answer(
        user_message=ctx["user_message"],
        page=ctx["page"],
        page_context=ctx["page_context"],
        tool_context=ctx["tool_context"],
        sources=ctx["sources"],
        template_fallback=ctx["template_fallback"],
        reasoning=ctx.get("reasoning"),
    )
    # Enforce: no suggested_actions for forbidden/out_of_scope operations
    reasoning = ctx.get("reasoning")
    strip = reasoning and (reasoning.should_refuse_or_limit or reasoning.request_type == "out_of_scope")
    safe_actions = [] if strip else ctx.get("suggested_actions", [])
    return ChatResponse(
        answer=llm_answer,
        session_id=body.session_id or str(uuid.uuid4()),
        sources=ctx["sources"],
        suggested_actions=safe_actions,
    )


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.warning("ENTER_STREAM_CHAT message=%s page=%s", body.message[:80], body.page)
    logger.warning("TRACE_PAGE_CONTEXT raw_page_context=%s", json.dumps(body.page_context, ensure_ascii=False))
    logger.warning("TRACE_PAGE_CONTEXT_TIME raw_local_hour=%s raw_local_minute=%s local_time_text=%s timezone=%s",
                   body.page_context.get('local_hour'),
                   body.page_context.get('local_minute'),
                   body.page_context.get('local_time_text'),
                   body.page_context.get('timezone'))
    ctx = await build_assistant_context(db, body, str(current_user.id))
    logger.warning("TRACE_ASSISTANT_INTENT intent=%s", [s.get('type','?') for s in ctx.get('sources',[])])
    session_id = body.session_id or str(uuid.uuid4())

    reasoning = ctx.get("reasoning")

    async def event_generator():
        try:
            async for delta in generate_assistant_answer_stream(
                user_message=ctx["user_message"],
                page=ctx["page"],
                page_context=ctx["page_context"],
                tool_context=ctx["tool_context"],
                sources=ctx["sources"],
                template_fallback=ctx["template_fallback"],
                reasoning=reasoning,
            ):
                if delta:
                    yield format_sse("message", {"delta": delta})
            yield format_sse("source", {"sources": ctx["sources"]})
            # Enforce: no suggested_actions for forbidden/out_of_scope operations
            strip = reasoning and (reasoning.should_refuse_or_limit or reasoning.request_type == "out_of_scope")
            actions = [] if strip else ctx.get("suggested_actions", [])
            if actions:
                yield format_sse("action", {"suggested_actions": actions})
            yield format_sse("done", {"session_id": session_id})
        except asyncio.CancelledError:
            return
        except Exception:
            yield format_sse("error", {"message": "AI 助手暂时不可用，请稍后再试"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/actions/execute", response_model=AssistantActionExecuteResponse)
async def execute_action(
    body: AssistantActionExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = str(current_user.id)
    logger.warning("TRACE_ASSISTANT_ACTION_EXECUTE_START action_type=%s", body.type)

    # Phase 17: Tool registry pre-check
    from app.services.tool_registry import is_tool_allowed, get_tool_spec
    ctx = {"confirmed_by_user": True, "action_type": body.type, "source": "assistant_action_execute_endpoint"}
    if not is_tool_allowed("execute_assistant_action", ctx):
        logger.warning("TRACE_TOOL_REGISTRY_ACTION_BLOCKED action_type=%s", body.type)
        return AssistantActionExecuteResponse(ok=False, type=body.type, message="该操作需要用户确认")

    tool_spec = get_tool_spec("execute_assistant_action")
    risk_level = tool_spec.risk_level if tool_spec else "medium"
    requires_conf = tool_spec.requires_confirmation if tool_spec else True

    # Phase 18: Audit — try read before_snapshot (failure must not block action)
    before_snapshot = None
    if body.type == "save_current_record":
        try:
            from app.services.assistant_tools import get_dashboard_snapshot, get_record_detail_snapshot
            rid = body.payload.get("record_id", "")
            rec_before = await get_record_detail_snapshot(db, user_id, rid) if rid else None
            dash_before = await get_dashboard_snapshot(db, user_id)
            before_snapshot = {
                "record_id": rid,
                "was_saved": rec_before.get("is_confirmed") if rec_before else None,
                "record_calories": rec_before.get("calories") if rec_before else None,
                "today_calories_before": dash_before.get("consumed_calories"),
                "target_calories_before": dash_before.get("target_calories"),
                "remaining_calories_before": dash_before.get("remaining_calories"),
            }
            logger.warning("TRACE_ACTION_AUDIT_BEFORE_SNAPSHOT action_type=%s available=true", body.type)
        except Exception as snap_exc:
            logger.warning("TRACE_ACTION_AUDIT_BEFORE_SNAPSHOT action_type=%s available=false error=%s",
                           body.type, str(snap_exc)[:200])

    # Phase 18: Audit — create pending log (failure must not block action)
    from app.services.assistant_action_audit import create_action_audit_log, mark_action_audit_success, mark_action_audit_failed
    audit_log = await create_action_audit_log(
        db, user_id, body.action_id, body.type, body.payload,
        risk_level=risk_level, requires_confirmation=requires_conf,
        before_snapshot=before_snapshot,
    )
    audit_log_id = str(audit_log.id) if audit_log else None
    if audit_log_id is None:
        logger.warning("TRACE_ACTION_AUDIT_FAILED stage=create_pending action_type=%s (action will proceed)", body.type)

    # Execute the action
    result = await execute_assistant_action(db, user_id, body.type, body.payload)

    if not result.get("ok"):
        # Action failed — mark audit as failed (must not block response)
        if audit_log_id:
            err_msg = result.get("message", "未知错误")
            await mark_action_audit_failed(db, audit_log_id, err_msg, result)
        logger.warning(
            "TRACE_ASSISTANT_ACTION_EXECUTE_RESPONSE has_observation=false has_followup=false (action failed)"
        )
        return AssistantActionExecuteResponse(**result)

    # Action succeeded
    logger.warning("TRACE_ASSISTANT_ACTION_EXECUTE_SUCCESS action_type=%s", body.type)

    # Observer: re-read business state after action succeeds
    after_snapshot = None
    obs_warning = False
    try:
        from app.services.assistant_observer import observe_after_action
        obs = await observe_after_action(db, user_id, body.type, result, body.payload)
        if obs:
            result["post_action_observation"] = obs.get("post_action_observation")
            result["assistant_followup_message"] = obs.get("assistant_followup_message")
            # Extract after_snapshot from observer
            post_obs = obs.get("post_action_observation", {}) or {}
            if post_obs:
                dash_after = post_obs.get("dashboard_after", {})
                rec_after = post_obs.get("record", {})
                after_snapshot = {
                    "record_id": rec_after.get("id", ""),
                    "is_saved": True,
                    "record_calories": rec_after.get("calories"),
                    "today_calories_after": dash_after.get("today_calories"),
                    "target_calories_after": dash_after.get("target_calories"),
                    "remaining_calories_after": dash_after.get("remaining_calories"),
                }
    except Exception as obs_exc:
        logger.warning("TRACE_ASSISTANT_OBSERVER_FAILED action_type=%s error=%s", body.type, obs_exc)
        obs_warning = True

    # Phase 18: Audit — mark success (must not block response)
    if audit_log_id:
        if obs_warning:
            result["observer_warning"] = True
        await mark_action_audit_success(db, audit_log_id, result, after_snapshot)

    logger.warning(
        "TRACE_ASSISTANT_ACTION_EXECUTE_RESPONSE has_observation=%s has_followup=%s",
        result.get("post_action_observation") is not None,
        bool(result.get("assistant_followup_message")),
    )
    return AssistantActionExecuteResponse(**result)
