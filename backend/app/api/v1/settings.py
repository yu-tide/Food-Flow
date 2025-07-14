from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    RecommendTargetsRequest,
    RecommendTargetsResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
)

router = APIRouter(prefix="/users", tags=["用户设置"])

# Field names on UserSettings that also exist on User (for backward compat sync)
_USER_SYNC_FIELDS = ("target_calories", "target_protein", "target_carbs", "target_fat", "goal_type")


async def _get_or_create_settings(db: AsyncSession, user: User) -> UserSettings:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        await db.flush()
    return settings


@router.get("/me/settings", response_model=UserSettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await _get_or_create_settings(db, current_user)
    return UserSettingsResponse.model_validate(settings)


@router.patch("/me/settings", response_model=UserSettingsResponse)
async def update_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await _get_or_create_settings(db, current_user)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return UserSettingsResponse.model_validate(settings)

    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)
        # Sync nutrition targets to User model for backward compat
        if field in _USER_SYNC_FIELDS:
            setattr(current_user, field, value)

    await db.commit()
    await db.refresh(settings)
    return UserSettingsResponse.model_validate(settings)


@router.post("/me/settings/recommend-targets", response_model=RecommendTargetsResponse)
async def recommend_targets(
    body: RecommendTargetsRequest,
    current_user: User = Depends(get_current_user),
):
    """Mifflin-St Jeor BMR + TDEE calculation with goal adjustments."""
    w, h, a = body.weight_kg, body.height_cm, body.age
    g = body.gender

    if g == "male":
        bmr = 10 * w + 6.25 * h - 5 * a + 5
    elif g == "female":
        bmr = 10 * w + 6.25 * h - 5 * a - 161
    else:
        bmr = 10 * w + 6.25 * h - 5 * a - 78

    activity_factors = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
    act_factor = activity_factors.get(body.activity_level, 1.375)

    tdee = bmr * act_factor

    goal_adjustments = {"maintain": 0, "lose": -400, "gain": 300}
    goal_adj = goal_adjustments.get(body.goal_type, 0)

    calories = max(1200, round((tdee + goal_adj) / 50) * 50)

    protein_multipliers = {"maintain": 1.6, "lose": 1.8, "gain": 2.0}
    protein = max(40, round(w * protein_multipliers.get(body.goal_type, 1.6) / 5) * 5)

    fat_ratio = 0.22 if body.goal_type == "gain" else 0.25
    fat = max(30, round((calories * fat_ratio) / 9 / 5) * 5)

    carbs = max(50, round((calories - protein * 4 - fat * 9) / 4 / 5) * 5)

    goal_labels = {"maintain": "维持体重", "lose": "减重", "gain": "增重"}
    explanation = (
        f"基于{body.gender}、{body.age}岁、{body.height_cm}cm、{body.weight_kg}kg，"
        f"活动等级{body.activity_level}，目标{goal_labels.get(body.goal_type, body.goal_type)}。"
        f"BMR={bmr:.0f}kcal，TDEE={tdee:.0f}kcal，目标调整{goal_adj:+d}kcal。"
        f"推荐每日{calories}kcal，蛋白质{protein}g，脂肪{fat}g，碳水{carbs}g。"
    )

    return RecommendTargetsResponse(
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        bmr=round(bmr, 1),
        tdee=round(tdee, 1),
        activity_factor=act_factor,
        goal_adjustment=goal_adj,
        explanation=explanation,
    )
