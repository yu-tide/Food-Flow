"""record_tool — 饮食记录查询与管理工具

原始依赖：assistant_tools（get_dashboard_snapshot / get_weekly_snapshot 等）
"""

from __future__ import annotations
import logging

from app.services.agent.tools.registry import ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)


@ToolRegistry.register(ToolSpec(
    name="dashboard_snapshot",
    description="获取今日营养仪表盘数据（已摄入热量、剩余热量、宏量营养素、记录数）",
    risk_level="none",
    requires_context=["db", "user_id"],
    timeout_seconds=10,
    categories=["record"],
))
async def get_dashboard(db, user_id: str) -> dict:
    """今日仪表盘快照"""
    from app.services.assistant_tools import get_dashboard_snapshot as _get
    return await _get(db, user_id)


@ToolRegistry.register(ToolSpec(
    name="daily_snapshot",
    description="查询指定日期的饮食记录汇总",
    risk_level="none",
    requires_context=["db", "user_id"],
    timeout_seconds=10,
    categories=["record"],
))
async def daily_snapshot(
    db,
    user_id: str,
    target_date: str,
    timezone: str = "Asia/Shanghai",
    date_label: str | None = None,
) -> dict:
    """指定日期快照"""
    from app.services.assistant_tools import get_daily_snapshot as _get
    return await _get(db, user_id, target_date, timezone, date_label)


@ToolRegistry.register(ToolSpec(
    name="weekly_snapshot",
    description="获取本周饮食统计汇总（日均热量、各日详情、宏量营养素）",
    risk_level="none",
    requires_context=["db", "user_id"],
    timeout_seconds=10,
    categories=["record"],
))
async def weekly_snapshot(db, user_id: str) -> dict:
    """本周统计快照"""
    from app.services.assistant_tools import get_weekly_snapshot as _get
    return await _get(db, user_id)


@ToolRegistry.register(ToolSpec(
    name="record_detail",
    description="获取单条饮食记录的完整详情（成分列表、宏量营养素、保存状态）",
    risk_level="none",
    requires_context=["db", "user_id"],
    timeout_seconds=10,
    categories=["record"],
))
async def record_detail(db, user_id: str, record_id: str) -> dict | None:
    """单条记录详情"""
    from app.services.assistant_tools import get_record_detail_snapshot as _get
    return await _get(db, user_id, record_id)


@ToolRegistry.register(ToolSpec(
    name="settings_snapshot",
    description="获取当前用户的营养目标设置（目标热量、目标蛋白/碳水/脂肪、类型）",
    risk_level="none",
    requires_context=["db", "user_id"],
    timeout_seconds=10,
    categories=["record"],
))
async def settings_snapshot(db, user_id: str) -> dict:
    """用户设置快照"""
    from app.services.assistant_tools import get_settings_snapshot as _get
    return await _get(db, user_id)


@ToolRegistry.register(ToolSpec(
    name="recent_records",
    description="查询最近 N 条已确认的饮食记录",
    risk_level="none",
    requires_context=["db", "user_id"],
    timeout_seconds=10,
    categories=["record"],
))
async def recent_records(db, user_id: str, limit: int = 5) -> list[dict]:
    """最近已确认记录"""
    from app.services.assistant_tools import search_recent_confirmed as _search
    return await _search(db, user_id, limit)
