"""nutrition_tool — 营养检索与估算工具

原始依赖：nutrition_retriever / nutrition_estimator / food_normalizer
"""

from __future__ import annotations
import logging

from app.services.agent.tools.registry import ToolRegistry, ToolSpec
from app.services.food_normalizer import normalize_food_name
from app.services.nutrition_retriever import retrieve_nutrition_references

logger = logging.getLogger(__name__)


@ToolRegistry.register(ToolSpec(
    name="nutrition_retrieve",
    description="根据食物名称和重量检索营养数据（热量、蛋白质、碳水、脂肪）",
    risk_level="none",
    requires_context=["db"],
    timeout_seconds=10,
    categories=["nutrition"],
))
async def nutrition_retrieve(
    food_name: str,
    weight_g: float = 100.0,
    db=None,
    category_hint: str | None = None,
) -> dict:
    """营养检索：归一化 → 检索 → 加权估算"""
    norm = normalize_food_name(food_name, category_hint or "", None)
    refs = retrieve_nutrition_references(
        food_name=norm["normalized_name"],
        category=norm["category"],
        search_queries=norm["search_queries"],
    )
    if refs:
        best = refs[0]
        scale = weight_g / 100.0
        cal = round((best.calories_per_100g or 0) * scale, 1)
        pro = round((best.protein_per_100g or 0) * scale, 1)
        carb = round((best.carbs_per_100g or 0) * scale, 1)
        fat = round((best.fat_per_100g or 0) * scale, 1)
        return {
            "food_name": food_name,
            "weight_g": weight_g,
            "calories": cal,
            "protein": pro,
            "carbs": carb,
            "fat": fat,
            "confidence": best.confidence,
            "source": "rag",
        }

    return {
        "food_name": food_name,
        "weight_g": weight_g,
        "note": "无匹配的营养参考数据",
    }


@ToolRegistry.register(ToolSpec(
    name="nutrition_estimate",
    description="估算单个食物项目的完整营养数据（含 AI 兜底）",
    risk_level="none",
    timeout_seconds=10,
    categories=["nutrition"],
))
async def nutrition_estimate(
    food_name: str,
    weight_g: float = 200.0,
    category: str = "mixed",
) -> dict:
    """营养估算：复用现有的 nutrition_estimator"""
    from app.schemas.ai_food import RecognizedFoodItem
    from app.services.nutrition_estimator import estimate_nutrition

    item = RecognizedFoodItem(
        food_name=food_name,
        estimated_weight_g=weight_g,
        category=category,
        source="tool",
    )
    result = estimate_nutrition(item)

    return {
        "food_name": food_name,
        "weight_g": weight_g,
        "calories": round(result.calories, 1),
        "protein": round(result.protein, 1),
        "carbs": round(result.carbs, 1),
        "fat": round(result.fat, 1),
        "confidence": round(result.confidence, 2),
        "source": result.source,
        "estimated": result.estimated,
        "reasoning": result.reasoning,
    }
