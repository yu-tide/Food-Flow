"""Read-only assistant tools — all statistics use confirmed records only."""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food_item import FoodItem
from app.models.food_record import FoodRecord
from app.models.user_settings import UserSettings

logger = logging.getLogger(__name__)

_WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


async def get_dashboard_snapshot(db: AsyncSession, user_id: str) -> dict:
    """Today's nutrition summary from confirmed records."""
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    result = await db.execute(
        select(FoodRecord).where(
            FoodRecord.user_id == user_id,
            FoodRecord.status == "confirmed",
            FoodRecord.created_at >= start,
            FoodRecord.created_at < end,
        )
    )
    records = result.scalars().all()

    total_cal = sum(r.total_calories or 0 for r in records)
    total_pro = sum(r.protein or 0 for r in records)
    total_carb = sum(r.carbohydrate or 0 for r in records)
    total_fat = sum(r.fat or 0 for r in records)

    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    user_settings = settings_result.scalar_one_or_none()
    target_cal = user_settings.target_calories if user_settings else 2000

    return {
        "date": start.strftime("%Y-%m-%d"),
        "consumed_calories": total_cal,
        "target_calories": target_cal,
        "remaining_calories": max(target_cal - total_cal, 0),
        "protein": total_pro,
        "carbs": total_carb,
        "fat": total_fat,
        "record_count": len(records),
    }


async def get_daily_snapshot(
    db: AsyncSession,
    user_id: str,
    target_date: str,
    timezone_str: str = "Asia/Shanghai",
    date_label: str | None = None,
) -> dict:
    """Query confirmed records for a specific calendar date in the user's local timezone.

    Uses FoodRecord.created_at (the only reliable timestamp on FoodRecord).
    Does NOT use server UTC date for "yesterday" — computes from timezone.
    """
    from datetime import datetime, timedelta, timezone as dt_timezone
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(timezone_str)
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")

    # Parse target_date "2026-05-17" into local day boundaries
    try:
        local_midnight = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=tz)
    except ValueError:
        local_midnight = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert local day boundaries to UTC for DB query
    utc_start = local_midnight.astimezone(dt_timezone.utc)
    utc_end = utc_start + timedelta(days=1)

    result = await db.execute(
        select(FoodRecord).where(
            FoodRecord.user_id == user_id,
            FoodRecord.status == "confirmed",
            FoodRecord.created_at >= utc_start,
            FoodRecord.created_at < utc_end,
        )
    )
    records = result.scalars().all()

    total_cal = sum(r.total_calories or 0 for r in records)
    total_pro = sum(r.protein or 0 for r in records)
    total_carb = sum(r.carbohydrate or 0 for r in records)
    total_fat = sum(r.fat or 0 for r in records)

    logger.warning(
        "TRACE_DAILY_SNAPSHOT_RESULT date=%s date_label=%s record_count=%s total_calories=%s timezone=%s",
        target_date, date_label or "?", len(records), total_cal, timezone_str,
    )

    # Batch-lookup food names from FoodItem (FoodRecord has no name column)
    record_ids = [r.id for r in records[:20]]
    food_name_map: dict[str, str] = {}
    if record_ids:
        name_result = await db.execute(
            select(FoodItem.record_id, FoodItem.food_name)
            .where(FoodItem.record_id.in_(record_ids))
            .order_by(FoodItem.sort_order.asc())
        )
        for row in name_result.all():
            if row.record_id not in food_name_map:
                food_name_map[str(row.record_id)] = row.food_name or "未命名记录"

    return {
        "date": target_date,
        "date_label": date_label or target_date,
        "record_count": len(records),
        "total_calories": total_cal,
        "protein": total_pro,
        "carbs": total_carb,
        "fat": total_fat,
        "records": [
            {
                "id": str(r.id),
                "name": food_name_map.get(str(r.id), "未命名记录"),
                "calories": r.total_calories or 0,
                "protein": r.protein or 0,
                "carbs": r.carbohydrate or 0,
                "fat": r.fat or 0,
            }
            for r in records[:20]
        ],
    }


async def get_weekly_snapshot(db: AsyncSession, user_id: str) -> dict:
    """This week's nutrition summary from confirmed records."""
    today = date.today()
    start_date = today - timedelta(days=6)
    start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
    end_dt = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) + timedelta(days=1)

    result = await db.execute(
        select(
            func.date(FoodRecord.created_at).label("day"),
            func.coalesce(func.sum(FoodRecord.total_calories), 0).label("calories"),
            func.coalesce(func.sum(FoodRecord.protein), 0).label("protein"),
            func.coalesce(func.sum(FoodRecord.carbohydrate), 0).label("carbs"),
            func.coalesce(func.sum(FoodRecord.fat), 0).label("fat"),
            func.count(FoodRecord.id).label("count"),
        )
        .where(
            FoodRecord.user_id == user_id,
            FoodRecord.status == "confirmed",
            FoodRecord.created_at >= start_dt,
            FoodRecord.created_at < end_dt,
        )
        .group_by(func.date(FoodRecord.created_at))
        .order_by("day")
    )
    rows = {str(r.day): r for r in result.all()}

    daily = []
    total_cal = 0
    total_pro = 0
    total_carb = 0
    total_fat = 0
    total_count = 0

    for i in range(7):
        d = start_date + timedelta(days=i)
        key = d.isoformat()
        r = rows.get(key)
        cal = int(r.calories) if r else 0
        pro = int(r.protein) if r else 0
        carb = int(r.carbs) if r else 0
        fat = int(r.fat) if r else 0
        cnt = int(r.count) if r else 0
        daily.append({"day": _WEEKDAY_NAMES[d.weekday()], "calories": cal})
        total_cal += cal
        total_pro += pro
        total_carb += carb
        total_fat += fat
        total_count += cnt

    return {
        "week_start": start_date.isoformat(),
        "week_end": today.isoformat(),
        "daily": daily,
        "avg_daily_calories": round(total_cal / 7),
        "total_calories": total_cal,
        "total_protein": total_pro,
        "total_carbs": total_carb,
        "total_fat": total_fat,
        "record_count": total_count,
    }


async def get_record_detail_snapshot(db: AsyncSession, user_id: str, record_id: str) -> dict | None:
    """Single record detail. Does NOT require confirmed — but notes status."""
    result = await db.execute(
        select(FoodRecord).where(FoodRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if record is None or str(record.user_id) != str(user_id):
        return None

    items_result = await db.execute(
        select(FoodItem)
        .where(FoodItem.record_id == record_id)
        .order_by(FoodItem.sort_order.asc())
    )
    food_items = items_result.scalars().all()

    components = []
    for item in food_items:
        for c in (item.components or []):
            components.append({
                "name": c.get("name", ""),
                "weight": c.get("estimated_weight_g"),
                "calories": c.get("calories"),
            })

    return {
        "id": str(record.id),
        "name": food_items[0].food_name if food_items else "未知",
        "status": record.status,
        "is_confirmed": record.status == "confirmed",
        "weight": food_items[0].weight if food_items else "0g",
        "calories": record.total_calories,
        "protein": record.protein,
        "carbs": record.carbohydrate,
        "fat": record.fat,
        "meal_type": record.meal_type,
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "components": components[:10],
        "component_count": len(components),
    }


async def get_settings_snapshot(db: AsyncSession, user_id: str) -> dict:
    """Current user nutrition targets."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if settings:
        return {
            "target_calories": settings.target_calories or 2000,
            "target_protein": settings.target_protein,
            "target_carbs": settings.target_carbs,
            "target_fat": settings.target_fat,
            "goal_type": settings.goal_type or "maintain",
            "nutrition_goal_mode": settings.nutrition_goal_mode or "agent_recommended",
            # Phase 16: expose user preferences for memory context
            "avoid_foods": settings.avoid_foods or "",
            "allergens": settings.allergens or "",
            "cuisines": settings.cuisines or [],
            "taste_preference": settings.taste_preference or "normal",
            "diet_style": settings.diet_style or "normal",
        }
    return {
        "target_calories": 2000,
        "target_protein": None,
        "target_carbs": None,
        "target_fat": None,
        "goal_type": "maintain",
        "nutrition_goal_mode": "agent_recommended",
        "avoid_foods": "",
        "allergens": "",
        "cuisines": [],
        "taste_preference": "normal",
        "diet_style": "normal",
    }


async def search_recent_confirmed(db: AsyncSession, user_id: str, limit: int = 5) -> list[dict]:
    """Recent confirmed records only."""
    result = await db.execute(
        select(FoodRecord)
        .where(
            FoodRecord.user_id == user_id,
            FoodRecord.status == "confirmed",
        )
        .order_by(FoodRecord.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()

    items = []
    for r in records:
        food_result = await db.execute(
            select(FoodItem.food_name)
            .where(FoodItem.record_id == r.id)
            .order_by(FoodItem.sort_order.asc())
            .limit(1)
        )
        name = food_result.scalar_one_or_none() or "未知"
        items.append({
            "id": str(r.id),
            "name": name,
            "calories": r.total_calories or 0,
            "protein": r.protein or 0,
            "carbs": r.carbohydrate or 0,
            "fat": r.fat or 0,
            "meal_type": r.meal_type,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        })
    return items
