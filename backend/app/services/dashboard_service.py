from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from app.models.analyze_task import AnalyzeTask
from app.models.food_record import FoodRecord
from app.models.user import User
from app.schemas.dashboard import (
    ActiveTaskItem,
    DashboardResponse,
    DashboardUser,
    MacroItem,
    RecentMealItem,
    TodaySummary,
    WeeklyPoint,
)
from app.schemas.tasks import current_step, estimate_text, status_text

MEAL_LABELS = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}

MACRO_TARGETS = {"protein": 120, "carbs": 250, "fat": 70}
MACRO_LABELS = {"protein": "蛋白质", "carbs": "碳水", "fat": "脂肪"}

_WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _today_range():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


async def _today_food_records(db: AsyncSession, user_id: str):
    start, end = _today_range()
    result = await db.execute(
        select(FoodRecord).where(
            FoodRecord.user_id == user_id,
            FoodRecord.status == "confirmed",
            FoodRecord.created_at >= start,
            FoodRecord.created_at < end,
        )
    )
    return result.scalars().all()


async def _build_user(user: User) -> DashboardUser:
    return DashboardUser(
        nickname=user.nickname,
        phone=user.phone,
        avatarText=user.avatar_text or "",
    )


def _build_today(records: list[FoodRecord], target: int = 2000) -> TodaySummary:
    consumed = sum(r.total_calories or 0 for r in records)
    remaining = max(target - consumed, 0)

    if consumed == 0:
        status_text_val = "今天还没有记录饮食"
    elif consumed < 1600:
        status_text_val = "摄入偏少，注意补充营养"
    elif consumed <= 2200:
        status_text_val = "摄入较均衡"
    else:
        status_text_val = "今日摄入偏高"

    return TodaySummary(
        consumedCalories=consumed,
        targetCalories=target,
        remainingCalories=remaining,
        statusText=status_text_val,
    )


def _build_macros(records: list[FoodRecord]) -> list[MacroItem]:
    protein_sum = sum(r.protein or 0 for r in records)
    carbs_sum = sum(r.carbohydrate or 0 for r in records)
    fat_sum = sum(r.fat or 0 for r in records)

    current_values = {"protein": protein_sum, "carbs": carbs_sum, "fat": fat_sum}

    return [
        MacroItem(
            key=key,
            label=MACRO_LABELS[key],
            current=current_values[key],
            target=MACRO_TARGETS[key],
            unit="g",
            percent=round(current_values[key] / MACRO_TARGETS[key] * 100),
        )
        for key in ("protein", "carbs", "fat")
    ]


async def _build_weekly(db: AsyncSession, user_id: str) -> list[WeeklyPoint]:
    today = date.today()
    seven_days_ago = today - timedelta(days=6)

    start_dt = datetime(seven_days_ago.year, seven_days_ago.month, seven_days_ago.day, tzinfo=timezone.utc)
    end_dt = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) + timedelta(days=1)

    result = await db.execute(
        select(
            func.date(FoodRecord.created_at).label("day"),
            func.sum(FoodRecord.total_calories).label("calories"),
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
    rows = {str(row.day): (row.calories or 0) for row in result.all()}

    points = []
    for i in range(7):
        d = seven_days_ago + timedelta(days=i)
        day_key = d.isoformat()
        points.append(WeeklyPoint(
            day=_WEEKDAY_NAMES[d.weekday()],
            calories=int(rows.get(day_key, 0)),
        ))
    return points


async def _build_active_task(db: AsyncSession, user_id: str) -> ActiveTaskItem | None:
    result = await db.execute(
        select(AnalyzeTask)
        .where(
            AnalyzeTask.user_id == user_id,
            AnalyzeTask.status.notin_(["SUCCESS", "FAILED"]),
        )
        .order_by(AnalyzeTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None
    return ActiveTaskItem(
        id=str(task.id),
        filename=task.filename,
        status=task.status,
        statusText=status_text(task.status),
        estimateText=estimate_text(task.status, task.eta_seconds),
        currentStep=current_step(task.status),
    )


def _make_title(record: FoodRecord) -> str:
    if record.summary:
        first_line = record.summary.split("\n")[0].strip()
        if first_line:
            return first_line[:40]
    if record.ocr_text:
        first = record.ocr_text.split("、")[0].strip()
        if first:
            return first[:40]
    return MEAL_LABELS.get(record.meal_type, record.meal_type)


def _format_time(dt: datetime | None) -> str:
    if dt is None:
        return ""
    local = dt.astimezone(timezone.utc).astimezone()
    return local.strftime("%H:%M")


async def _build_recent_meals(db: AsyncSession, user_id: str) -> list[RecentMealItem]:
    result = await db.execute(
        select(FoodRecord)
        .where(FoodRecord.user_id == user_id)
        .where(FoodRecord.status == "confirmed")
        .order_by(FoodRecord.created_at.desc())
        .limit(3)
    )
    records = result.scalars().all()

    return [
        RecentMealItem(
            id=str(r.id),
            mealType=r.meal_type,
            title=_make_title(r),
            time=_format_time(r.created_at),
            calories=r.total_calories or 0,
            summary=r.summary,
            protein=r.protein or 0,
            carbs=r.carbohydrate or 0,
            fat=r.fat or 0,
            imageUrl=r.image_url,
        )
        for r in records
    ]


async def _compute_streak(db: AsyncSession, user_id: str) -> int:
    """连续记录天数。非食物记录也计入，同一天去重，遇断档停止。"""
    tz = ZoneInfo("Asia/Shanghai")
    result = await db.execute(
        select(FoodRecord.created_at)
        .where(FoodRecord.user_id == user_id)
        .where(FoodRecord.status == "confirmed")
        .order_by(FoodRecord.created_at.desc())
    )
    rows = result.scalars().all()

    record_dates: set[date] = set()
    for created_at in rows:
        if created_at is None:
            continue
        dt = created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        record_dates.add(dt.astimezone(tz).date())

    if not record_dates:
        return 0

    today = datetime.now(tz).date()

    if today in record_dates:
        cursor = today
    elif today - timedelta(days=1) in record_dates:
        cursor = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in record_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def get_dashboard_summary(db: AsyncSession, user: User) -> DashboardResponse:
    user_id = str(user.id)

    today_records = await _today_food_records(db, user_id)
    streak = await _compute_streak(db, user_id)

    return DashboardResponse(
        user=await _build_user(user),
        today=_build_today(today_records, target=user.target_calories or 2000),
        macros=_build_macros(today_records),
        weekly=await _build_weekly(db, user_id),
        activeTask=await _build_active_task(db, user_id),
        recentMeals=await _build_recent_meals(db, user_id),
        streakDays=streak,
    )
