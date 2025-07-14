"""Rule-based suggested action generation and execution."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food_record import FoodRecord
from app.schemas.assistant_actions import AssistantSuggestedAction
from app.services.assistant_tools import get_weekly_snapshot

ALLOWED_ACTION_TYPES = {"open_record_detail", "open_settings", "save_current_record", "export_weekly_report"}

# ── Generation ──

def _action_open_record_detail(record_id: str) -> AssistantSuggestedAction:
    return AssistantSuggestedAction(
        id=str(uuid.uuid4()),
        type="open_record_detail",
        title="打开记录详情",
        description="查看这条饮食记录的详细信息。",
        confirm_label="打开",
        cancel_label="取消",
        payload={"record_id": record_id},
        requires_confirmation=False,
        risk_level="low",
    )


def _action_open_settings() -> AssistantSuggestedAction:
    return AssistantSuggestedAction(
        id=str(uuid.uuid4()),
        type="open_settings",
        title="打开设置页",
        description="前往设置页查看或调整你的营养目标。",
        confirm_label="打开设置",
        cancel_label="取消",
        payload={},
        requires_confirmation=False,
        risk_level="low",
    )


def _action_save_current_record(record_id: str) -> AssistantSuggestedAction:
    return AssistantSuggestedAction(
        id=str(uuid.uuid4()),
        type="save_current_record",
        title="保存当前记录",
        description="保存后，这条饮食记录会变为 confirmed，并进入 Dashboard 和统计。",
        confirm_label="确认保存",
        cancel_label="先不保存",
        payload={"record_id": record_id},
        requires_confirmation=True,
        risk_level="medium",
    )


def _action_export_weekly_report() -> AssistantSuggestedAction:
    return AssistantSuggestedAction(
        id=str(uuid.uuid4()),
        type="export_weekly_report",
        title="生成每周饮食报告",
        description="基于 confirmed 记录生成本周饮食总结。",
        confirm_label="生成周报",
        cancel_label="取消",
        payload={"week_start": None, "week_end": None},
        requires_confirmation=True,
        risk_level="low",
    )


def build_suggested_actions(
    user_message: str,
    page: str,
    page_context: dict | None,
    tool_context: dict | None,
) -> list[AssistantSuggestedAction]:
    """Rule-based action generation. No LLM involved."""
    actions = []
    page = page or ""
    ctx = page_context or {}
    record_id = ctx.get("record_id", "")
    is_confirm_page = page.startswith("/confirm/")
    is_statistics_page = page.startswith("/statistics")

    # 1. Save current record (confirm page with record_id)
    if is_confirm_page and record_id and any(kw in user_message for kw in ("保存", "确认这顿", "保存当前", "可以保存了", "帮我保存")):
        actions.append(_action_save_current_record(record_id))

    # 2. Open record detail
    elif record_id and any(kw in user_message for kw in ("打开这条", "查看详情", "跳转到记录", "打开记录")):
        actions.append(_action_open_record_detail(record_id))

    # 3. Open settings
    if any(kw in user_message for kw in ("去设置", "调整目标", "修改我的目标", "怎么设置蛋白质目标", "设置目标", "打开设置")) and not page.startswith("/settings"):
        actions.append(_action_open_settings())

    # 4. Export weekly report
    if (is_statistics_page or any(kw in user_message for kw in ("导出周报", "生成周报", "给我这周报告", "导出本周", "生成报告", "这周报告"))) and not any(kw in user_message for kw in ("删除", "清空")):
        actions.append(_action_export_weekly_report())

    return actions


# ── Execution ──

async def execute_open_record_detail(db: AsyncSession, user_id: str, payload: dict) -> dict:
    rid = payload.get("record_id", "")
    if not rid:
        return {"ok": False, "message": "缺少 record_id"}
    result = await db.execute(select(FoodRecord).where(FoodRecord.id == rid))
    record = result.scalar_one_or_none()
    if not record or str(record.user_id) != user_id:
        return {"ok": False, "message": "记录不存在或无权访问"}
    return {"ok": True, "message": "正在打开记录详情。", "result": {"url": f"/records/{rid}"}}


async def execute_open_settings(db: AsyncSession, user_id: str, payload: dict) -> dict:
    return {"ok": True, "message": "正在打开设置页。", "result": {"url": "/settings"}}


async def execute_save_current_record(db: AsyncSession, user_id: str, payload: dict) -> dict:
    rid = payload.get("record_id", "")
    if not rid:
        return {"ok": False, "message": "缺少 record_id"}
    result = await db.execute(select(FoodRecord).where(FoodRecord.id == rid))
    record = result.scalar_one_or_none()
    if not record or str(record.user_id) != user_id:
        return {"ok": False, "message": "记录不存在或无权访问"}

    if record.status == "confirmed":
        return {"ok": True, "message": "这条记录已经保存过。"}

    if record.status == "failed":
        return {"ok": False, "message": "识别失败的记录不能直接保存，请重新上传或重新分析。"}

    record.status = "confirmed"
    from datetime import datetime, timezone
    record.confirmed_at = datetime.now(timezone.utc)
    record.status_label = "用户已确认"
    await db.commit()
    await db.refresh(record)
    return {"ok": True, "message": "已保存当前记录，现在会进入 Dashboard 和统计。", "result": {"record_id": rid, "status": "confirmed"}}


async def execute_export_weekly_report(db: AsyncSession, user_id: str, payload: dict) -> dict:
    week = await get_weekly_snapshot(db, user_id)
    if week["record_count"] == 0:
        return {"ok": True, "message": "本周暂无已保存记录，无法生成报告。"}

    content = (
        f"## 本周饮食报告\n\n"
        f"统计周期：{week['week_start']} 至 {week['week_end']}\n\n"
        f"### 总览\n"
        f"- 记录数：{week['record_count']} 条\n"
        f"- 平均每日热量：{week['avg_daily_calories']} kcal\n"
        f"- 总热量：{week['total_calories']} kcal\n"
        f"- 蛋白质合计：{week['total_protein']}g\n"
        f"- 碳水合计：{week['total_carbs']}g\n"
        f"- 脂肪合计：{week['total_fat']}g\n\n"
        f"### 每日热量\n"
    )
    for d in week["daily"]:
        content += f"- {d['day']}：{d['calories']} kcal\n"
    content += f"\n> 以上数据仅包含已保存（confirmed）记录。"
    return {"ok": True, "message": "已生成本周饮食报告。", "result": {"format": "markdown", "content": content}}


async def execute_assistant_action(db: AsyncSession, user_id: str, action_type: str, payload: dict) -> dict:
    if action_type not in ALLOWED_ACTION_TYPES:
        return {"ok": False, "type": action_type, "message": "不支持该操作类型"}

    if action_type == "open_record_detail":
        return await execute_open_record_detail(db, user_id, payload)
    if action_type == "open_settings":
        return await execute_open_settings(db, user_id, payload)
    if action_type == "save_current_record":
        return await execute_save_current_record(db, user_id, payload)
    if action_type == "export_weekly_report":
        return await execute_export_weekly_report(db, user_id, payload)

    return {"ok": False, "type": action_type, "message": "该操作暂未实现"}
