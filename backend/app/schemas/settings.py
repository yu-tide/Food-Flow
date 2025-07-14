from pydantic import BaseModel, ConfigDict


class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Body info
    gender: str | None = "unknown"
    age: int | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    activity_level: str | None = "light"
    target_weight_kg: int | None = None

    # Nutrition targets
    target_calories: int = 2000
    target_protein: int | None = None
    target_carbs: int | None = None
    target_fat: int | None = None
    goal_type: str = "maintain"
    nutrition_goal_mode: str = "agent_recommended"

    # Diet preferences
    diet_style: str | None = "normal"
    taste_preference: str | None = "normal"
    avoid_foods: str | None = None
    allergens: str | None = None
    cuisines: list[str] | None = []

    # AI preferences
    ai_recognition_mode: str = "standard"
    ai_estimate_mode: str = "standard"
    ai_low_confidence_confirm: bool = True
    ai_show_components: bool = True
    ai_show_summary: bool = True
    ai_confirm_similar_dish: bool = True

    # Notifications
    breakfast_reminder_enabled: bool = True
    breakfast_reminder_time: str | None = "08:30"
    lunch_reminder_enabled: bool = True
    lunch_reminder_time: str | None = "12:00"
    dinner_reminder_enabled: bool = True
    dinner_reminder_time: str | None = "18:30"
    daily_summary_enabled: bool = True
    daily_summary_time: str | None = "21:30"
    weekly_report_enabled: bool = True
    weekly_report_day: int | None = 7
    weekly_report_time: str | None = "10:00"
    inactivity_reminder_enabled: bool = True

    # Privacy
    image_retention_policy: str = "keep_history"
    allow_anonymous_ai_training: bool = False


class UserSettingsUpdate(BaseModel):
    """All fields optional — frontend sends only changed fields."""
    gender: str | None = None
    age: int | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    activity_level: str | None = None
    target_weight_kg: int | None = None
    target_calories: int | None = None
    target_protein: int | None = None
    target_carbs: int | None = None
    target_fat: int | None = None
    goal_type: str | None = None
    nutrition_goal_mode: str | None = None
    diet_style: str | None = None
    taste_preference: str | None = None
    avoid_foods: str | None = None
    allergens: str | None = None
    cuisines: list[str] | None = None
    ai_recognition_mode: str | None = None
    ai_estimate_mode: str | None = None
    ai_low_confidence_confirm: bool | None = None
    ai_show_components: bool | None = None
    ai_show_summary: bool | None = None
    ai_confirm_similar_dish: bool | None = None
    breakfast_reminder_enabled: bool | None = None
    breakfast_reminder_time: str | None = None
    lunch_reminder_enabled: bool | None = None
    lunch_reminder_time: str | None = None
    dinner_reminder_enabled: bool | None = None
    dinner_reminder_time: str | None = None
    daily_summary_enabled: bool | None = None
    daily_summary_time: str | None = None
    weekly_report_enabled: bool | None = None
    weekly_report_day: int | None = None
    weekly_report_time: str | None = None
    inactivity_reminder_enabled: bool | None = None
    image_retention_policy: str | None = None
    allow_anonymous_ai_training: bool | None = None


class RecommendTargetsRequest(BaseModel):
    gender: str = "unknown"
    age: int
    height_cm: int
    weight_kg: int
    activity_level: str = "light"
    goal_type: str = "maintain"


class RecommendTargetsResponse(BaseModel):
    calories: int
    protein: int
    carbs: int
    fat: int
    bmr: float
    tdee: float
    activity_factor: float
    goal_adjustment: int
    explanation: str
