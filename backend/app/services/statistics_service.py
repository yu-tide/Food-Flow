from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food_record import FoodRecord
from app.models.user import User
from app.schemas.statistics import (
    DailyCalories,
    LastWeekComparison,
    MacroTrendPoint,
    MealDistItem,
    WeeklyStatsResponse,
)

_WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

MEAL_COLORS = {
    "breakfast": "#FFB347",
    "lunch": "#4CAF50",
    "dinner": "#7B68EE",
    "snack": "#FF7043",
}
MEAL_LABELS = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}

PROTEIN_TARGET = 120
CARB_TARGET = 250


def _week_range(days: list[date]) -> str:
    if not days:
        return ""
    fmt = lambda d: f"{d.month}/{d.day}"
    return f"{fmt(days[0])} - {fmt(days[-1])}"


def _week_days() -> list[date]:
    today = date.today()
    start = today - timedelta(days=6)
    return [start + timedelta(days=i) for i in range(7)]


async def _query_week(db: AsyncSession, user_id: str, week_days: list[date]):
    start = datetime(week_days[0].year, week_days[0].month, week_days[0].day, tzinfo=timezone.utc)
    end = datetime(week_days[-1].year, week_days[-1].month, week_days[-1].day, tzinfo=timezone.utc) + timedelta(days=1)

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
            FoodRecord.created_at >= start,
            FoodRecord.created_at < end,
        )
        .group_by(func.date(FoodRecord.created_at))
        .order_by("day")
    )
    rows = {}
    for r in result.all():
        rows[str(r.day)] = r
    return rows


async def _query_meal_dist(db: AsyncSession, user_id: str, week_days: list[date]) -> list[MealDistItem]:
    start = datetime(week_days[0].year, week_days[0].month, week_days[0].day, tzinfo=timezone.utc)
    end = datetime(week_days[-1].year, week_days[-1].month, week_days[-1].day, tzinfo=timezone.utc) + timedelta(days=1)

    result = await db.execute(
        select(
            FoodRecord.meal_type,
            func.coalesce(func.sum(FoodRecord.total_calories), 0).label("calories"),
        )
        .where(
            FoodRecord.user_id == user_id,
            FoodRecord.status == "confirmed",
            FoodRecord.created_at >= start,
            FoodRecord.created_at < end,
        )
        .group_by(FoodRecord.meal_type)
    )
    return [
        MealDistItem(
            name=MEAL_LABELS.get(r.meal_type, r.meal_type),
            calories=int(r.calories),
            color=MEAL_COLORS.get(r.meal_type, "#9E9E9E"),
        )
        for r in result.all()
    ]


async def _get_week_summary(db: AsyncSession, user_id: str, week_days: list[date], target_calories: int = 2000):
    rows = await _query_week(db, user_id, week_days)

    daily_calories = []
    macro_trend = []
    total_cal = 0
    protein_days = 0
    carb_days = 0
    record_count = 0

    for d in week_days:
        key = d.isoformat()
        r = rows.get(key)
        cal = int(r.calories) if r else 0
        pro = int(r.protein) if r else 0
        carb = int(r.carbs) if r else 0
        fat = int(r.fat) if r else 0
        cnt = int(r.count) if r else 0

        daily_calories.append(DailyCalories(day=_WEEKDAY_NAMES[d.weekday()], calories=cal))
        macro_trend.append(MacroTrendPoint(day=_WEEKDAY_NAMES[d.weekday()], protein=pro, carbs=carb, fat=fat))
        total_cal += cal
        if pro >= PROTEIN_TARGET:
            protein_days += 1
        if carb >= CARB_TARGET:
            carb_days += 1
        record_count += cnt

    avg_daily = round(total_cal / 7)
    avg_meals = round(record_count / 7, 1)
    today_key = week_days[-1].isoformat()
    today_row = rows.get(today_key)
    today_cal = int(today_row.calories) if today_row else 0

    return daily_calories, macro_trend, total_cal, avg_daily, protein_days, carb_days, record_count, avg_meals, max(target_calories - today_cal, -999)


def _generate_ai_summary(avg_daily: int, protein_days: int, carb_days: int) -> list[str]:
    lines = []
    if avg_daily >= 1800:
        lines.append("本周饮食记录较稳定，建议继续保持。")
    elif avg_daily > 0:
        lines.append("本周饮食记录偏少，可以增加记录频率以获得更准确的分析。")
    else:
        lines.append("本周暂无饮食记录，开始记录吧！")

    if protein_days < 4:
        lines.append("蛋白质摄入仍有提升空间，可增加鸡蛋、鱼肉、豆制品。")
    if carb_days > 4:
        lines.append("建议控制高碳水餐次比例，增加蔬菜和优质脂肪。")
    if not lines:
        lines.append("营养搭配良好，继续保持！")
    return lines


async def get_weekly_stats(db: AsyncSession, user: User) -> WeeklyStatsResponse:
    week_days = _week_days()
    user_id = str(user.id)

    daily_cal, macro_trend, total_cal, avg_daily, protein_days, carb_days, rec_cnt, avg_meals, today_gap = await _get_week_summary(db, user_id, week_days, target_calories=user.target_calories or 2000)
    meal_dist = await _query_meal_dist(db, user_id, week_days)

    # last week comparison
    prev_days = [week_days[0] - timedelta(days=7 + i) for i in range(7)]
    _, _, p_total, p_avg, p_pro_days, _, p_rec, _, _ = await _get_week_summary(db, user_id, prev_days)

    avg_cal_delta = round((avg_daily - p_avg) / p_avg * 100) if p_avg else 0
    pro_delta = round((protein_days - p_pro_days) / max(p_pro_days, 1) * 100) if p_pro_days else 0

    comparison = LastWeekComparison(
        avg_calories_delta_pct=avg_cal_delta,
        protein_delta_pct=pro_delta,
        record_delta_days=rec_cnt - p_rec,
        avg_calories_last_week=p_avg,
        protein_last_week=p_pro_days,
        record_days_last_week=p_rec,
    )

    return WeeklyStatsResponse(
        week_range=_week_range(week_days),
        target_calories=user.target_calories or 2000,
        avg_daily_calories=avg_daily,
        total_calories=total_cal,
        protein_target_days=protein_days,
        high_carb_days=carb_days,
        record_count=rec_cnt,
        average_meals=avg_meals,
        today_gap=today_gap,
        daily_calories=daily_cal,
        macro_trend=macro_trend,
        meal_distribution=meal_dist,
        last_week_comparison=comparison,
        ai_summary=_generate_ai_summary(avg_daily, protein_days, carb_days),
    )
