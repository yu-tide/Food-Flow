"""calculator_tool — 热量与营养计算工具

纯函数工具，不依赖数据库，无副作用
"""

from __future__ import annotations
import logging

from app.services.agent.tools.registry import ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)


@ToolRegistry.register(ToolSpec(
    name="calorie_calculator",
    description="根据宏量营养素计算总热量：protein*4 + carbs*4 + fat*9",
    risk_level="none",
    timeout_seconds=3,
    categories=["calculation"],
))
async def calorie_calculator(
    protein_g: float = 0.0,
    carbs_g: float = 0.0,
    fat_g: float = 0.0,
) -> dict:
    """宏量营养素 → 热量换算"""
    cal = protein_g * 4 + carbs_g * 4 + fat_g * 9
    return {
        "calories": round(cal, 1),
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "formula": "protein*4 + carbs*4 + fat*9",
    }


@ToolRegistry.register(ToolSpec(
    name="bmr_calculator",
    description="计算基础代谢率 BMR（Mifflin-St Jeor 公式）",
    risk_level="none",
    timeout_seconds=3,
    categories=["calculation"],
))
async def bmr_calculator(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str = "male",
) -> dict:
    """BMR 计算"""
    if gender == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    return {
        "bmr": round(bmr, 1),
        "bmr_kcal_per_day": round(bmr, 1),
        "formula": "Mifflin-St Jeor",
        "inputs": {"weight_kg": weight_kg, "height_cm": height_cm, "age": age, "gender": gender},
    }


@ToolRegistry.register(ToolSpec(
    name="tdee_calculator",
    description="根据 BMR 和活动系数估算每日总能耗 TDEE",
    risk_level="none",
    timeout_seconds=3,
    categories=["calculation"],
))
async def tdee_calculator(
    bmr: float,
    activity_level: str = "moderate",
) -> dict:
    """TDEE 计算"""
    factors = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    factor = factors.get(activity_level, 1.55)
    tdee = bmr * factor

    return {
        "tdee": round(tdee, 1),
        "bmr": bmr,
        "activity_level": activity_level,
        "activity_factor": factor,
        "tdee_kcal_per_day": round(tdee, 1),
    }


@ToolRegistry.register(ToolSpec(
    name="macro_split",
    description="根据目标热量拆分推荐宏量营养素克数（蛋白/碳水/脂肪比例）",
    risk_level="none",
    timeout_seconds=3,
    categories=["calculation"],
))
async def macro_split(
    target_calories: float,
    protein_pct: float = 0.30,
    carbs_pct: float = 0.40,
    fat_pct: float = 0.30,
) -> dict:
    """宏量营养素拆分"""
    protein_g = (target_calories * protein_pct) / 4
    carbs_g = (target_calories * carbs_pct) / 4
    fat_g = (target_calories * fat_pct) / 9

    return {
        "target_calories": target_calories,
        "protein_g": round(protein_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_g": round(fat_g, 1),
        "protein_cal": round(target_calories * protein_pct, 1),
        "carbs_cal": round(target_calories * carbs_pct, 1),
        "fat_cal": round(target_calories * fat_pct, 1),
        "ratios": {"protein": protein_pct, "carbs": carbs_pct, "fat": fat_pct},
    }
