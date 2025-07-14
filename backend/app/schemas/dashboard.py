from typing import Optional

from pydantic import BaseModel


class DashboardUser(BaseModel):
    nickname: str
    phone: str = ""
    avatarText: str = ""


class TodaySummary(BaseModel):
    consumedCalories: int
    targetCalories: int
    remainingCalories: int
    statusText: str


class MacroItem(BaseModel):
    key: str
    label: str
    current: int
    target: int
    unit: str
    percent: int


class WeeklyPoint(BaseModel):
    day: str
    calories: int


class ActiveTaskItem(BaseModel):
    id: Optional[str] = None
    filename: Optional[str] = None
    status: Optional[str] = None
    statusText: Optional[str] = None
    estimateText: Optional[str] = None
    currentStep: Optional[int] = None


class RecentMealItem(BaseModel):
    id: str
    mealType: str
    title: str
    time: str
    calories: int
    summary: Optional[str] = None
    protein: int
    carbs: int
    fat: int
    imageUrl: Optional[str] = None


class DashboardResponse(BaseModel):
    user: DashboardUser
    today: TodaySummary
    macros: list[MacroItem]
    weekly: list[WeeklyPoint]
    activeTask: Optional[ActiveTaskItem] = None
    recentMeals: list[RecentMealItem] = []
    streakDays: int = 0
