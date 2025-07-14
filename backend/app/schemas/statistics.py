from pydantic import BaseModel


class DailyCalories(BaseModel):
    day: str
    calories: int


class MacroTrendPoint(BaseModel):
    day: str
    protein: int
    carbs: int
    fat: int


class MealDistItem(BaseModel):
    name: str
    calories: int
    color: str


class LastWeekComparison(BaseModel):
    avg_calories_delta_pct: int
    protein_delta_pct: int
    record_delta_days: int
    avg_calories_last_week: int
    protein_last_week: int
    record_days_last_week: int


class WeeklyStatsResponse(BaseModel):
    week_range: str
    target_calories: int = 2000
    avg_daily_calories: int = 0
    total_calories: int = 0
    protein_target_days: int = 0
    high_carb_days: int = 0
    record_count: int = 0
    average_meals: float = 0.0
    today_gap: int = 0
    daily_calories: list[DailyCalories] = []
    macro_trend: list[MacroTrendPoint] = []
    meal_distribution: list[MealDistItem] = []
    last_week_comparison: LastWeekComparison | None = None
    ai_summary: list[str] = []
