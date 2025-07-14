"""Post-action observer — re-reads business state after a safe action executes.

Generates a deterministic assistant_followup_message so the user sees
what changed, not just "action succeeded".
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.assistant_tools import get_dashboard_snapshot, get_record_detail_snapshot

logger = logging.getLogger(__name__)


async def observe_after_action(
    db: AsyncSession,
    user_id: str,
    action_type: str,
    action_result: dict,
    payload: dict | None = None,
) -> dict:
    """Re-read business state after a safe action succeeds.

    Returns {"post_action_observation": {...}, "assistant_followup_message": "..."}
    On any error: returns {} — observer failure must NOT roll back the action.
    """
    logger.warning("TRACE_ASSISTANT_OBSERVER_START action_type=%s", action_type)

    try:
        if action_type == "save_current_record":
            return await _observe_save_current_record(db, user_id, action_result, payload)
        elif action_type == "open_settings":
            return _observe_open_settings()
        elif action_type == "open_record_detail":
            return _observe_open_record_detail()
        elif action_type == "export_weekly_report":
            return {}  # markdown report already handled by frontend
        else:
            return {}
    except Exception as exc:
        logger.warning("TRACE_ASSISTANT_OBSERVER_FAILED action_type=%s error=%s", action_type, exc)
        return {}


# ── save_current_record ──

async def _observe_save_current_record(
    db: AsyncSession, user_id: str, action_result: dict, payload: dict | None
) -> dict:
    # Get record_id: action_result first, then payload, then give up
    rid = ""
    res = action_result.get("result") or {}
    rid = res.get("record_id", "")
    if not rid and payload:
        rid = payload.get("record_id", "")
    if not rid:
        logger.warning("TRACE_ASSISTANT_OBSERVER no record_id, skipping")
        return {}

    logger.warning("TRACE_ASSISTANT_OBSERVER_RECORD_LOADED record_id=%s", rid)

    # Re-read record (guaranteed to be confirmed now)
    record = await get_record_detail_snapshot(db, user_id, rid)
    if not record:
        logger.warning("TRACE_ASSISTANT_OBSERVER record %s not found or not owned by user %s", rid, user_id)
        return {}

    # Re-read dashboard (guaranteed to include the just-saved record now)
    dash = await get_dashboard_snapshot(db, user_id)

    consumed = dash.get("consumed_calories", 0)
    target = dash.get("target_calories", 2000)
    remaining = dash.get("remaining_calories", target)

    logger.warning("TRACE_ASSISTANT_OBSERVER_DASHBOARD_LOADED today_calories=%s remaining=%s", consumed, remaining)

    record_cal = record.get("calories", 0) or 0

    # Build deterministic followup — no LLM, no internal fields
    if consumed > 0 and remaining > 0:
        lines = [
            "已保存，这条记录现在会进入今日统计。",
            f"你今天已保存摄入约 {consumed} kcal，距离目标还剩约 {remaining} kcal。",
        ]
        if remaining > 1000:
            lines.append("热量预算还很充足，后面可以正常安排。")
        elif remaining > 400:
            lines.append("后面一餐可以优先选清淡蛋白质和蔬菜，避免油脂堆高。")
        else:
            lines.append("今天热量已接近目标，后面建议轻食，优先蔬菜和蛋白质。")
    elif consumed > 0:
        lines = [
            "已保存，这条记录现在会进入今日统计。",
            f"你今天已保存摄入约 {consumed} kcal。",
        ]
    else:
        # Shouldn't happen after save, but handle gracefully
        lines = [
            "已保存，这条记录现在会进入今日统计。",
            "当前暂时没能读取到完整今日统计，你可以稍后到 Dashboard 查看更新。",
        ]

    followup = "".join(lines)

    observation = {
        "action_type": "save_current_record",
        "record": {
            "id": rid,
            "calories": record_cal,
            "name": record.get("name", ""),
        },
        "dashboard_after": {
            "today_calories": consumed,
            "target_calories": target,
            "remaining_calories": remaining,
            "protein": dash.get("protein", 0),
            "carbs": dash.get("carbs", 0),
            "fat": dash.get("fat", 0),
        },
    }

    logger.warning("TRACE_ASSISTANT_OBSERVER_FOLLOWUP_CREATED action_type=save_current_record")
    return {"post_action_observation": observation, "assistant_followup_message": followup}


# ── open_settings ──

def _observe_open_settings() -> dict:
    return {"assistant_followup_message": "已为你打开设置页，你可以在这里调整目标热量和宏量营养目标。"}


# ── open_record_detail ──

def _observe_open_record_detail() -> dict:
    return {"assistant_followup_message": "已为你打开这条记录详情，你可以查看识别结果和营养估算。"}
