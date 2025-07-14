"""whole_dish / mixed 模式下，当 AI 没有返回 components 时，根据菜品类型自动生成 fallback components。"""
import logging

from app.schemas.ai_food import FoodComponent

logger = logging.getLogger(__name__)

# 菜品类型 → 默认成分模板
_FALLBACK_TEMPLATES: dict[str, list[dict]] = {
    "麻辣烫": [
        {"name": "肉类", "category": "protein", "estimated_weight_g": 80, "calories": 130, "confidence": 0.45},
        {"name": "丸子/加工肉", "category": "processed_protein", "estimated_weight_g": 120, "calories": 220, "confidence": 0.45},
        {"name": "豆制品", "category": "soy", "estimated_weight_g": 100, "calories": 120, "confidence": 0.4},
        {"name": "蔬菜", "category": "vegetable", "estimated_weight_g": 180, "calories": 60, "confidence": 0.55},
        {"name": "粉/面/主食类", "category": "carbs", "estimated_weight_g": 80, "calories": 160, "confidence": 0.35},
        {"name": "汤底/油脂", "category": "sauce_oil", "estimated_weight_g": None, "calories": 80, "confidence": 0.35},
    ],
    "冒菜": [
        {"name": "肉类", "category": "protein", "estimated_weight_g": 80, "calories": 130, "confidence": 0.45},
        {"name": "丸子/加工肉", "category": "processed_protein", "estimated_weight_g": 100, "calories": 180, "confidence": 0.45},
        {"name": "豆制品", "category": "soy", "estimated_weight_g": 80, "calories": 100, "confidence": 0.4},
        {"name": "蔬菜", "category": "vegetable", "estimated_weight_g": 200, "calories": 70, "confidence": 0.55},
        {"name": "粉/面/主食类", "category": "carbs", "estimated_weight_g": 60, "calories": 120, "confidence": 0.35},
        {"name": "汤底/油脂", "category": "sauce_oil", "estimated_weight_g": None, "calories": 70, "confidence": 0.35},
    ],
    "火锅": [
        {"name": "肉类", "category": "protein", "estimated_weight_g": 150, "calories": 280, "confidence": 0.45},
        {"name": "丸子/加工肉", "category": "processed_protein", "estimated_weight_g": 100, "calories": 180, "confidence": 0.4},
        {"name": "豆制品", "category": "soy", "estimated_weight_g": 80, "calories": 100, "confidence": 0.4},
        {"name": "蔬菜", "category": "vegetable", "estimated_weight_g": 150, "calories": 50, "confidence": 0.55},
        {"name": "主食/粉面", "category": "carbs", "estimated_weight_g": 80, "calories": 150, "confidence": 0.35},
        {"name": "汤底/锅底", "category": "sauce_oil", "estimated_weight_g": None, "calories": 100, "confidence": 0.35},
    ],
    "麻辣香锅": [
        {"name": "肉类", "category": "protein", "estimated_weight_g": 100, "calories": 200, "confidence": 0.45},
        {"name": "丸子/加工肉", "category": "processed_protein", "estimated_weight_g": 80, "calories": 150, "confidence": 0.4},
        {"name": "豆制品", "category": "soy", "estimated_weight_g": 80, "calories": 100, "confidence": 0.4},
        {"name": "蔬菜", "category": "vegetable", "estimated_weight_g": 150, "calories": 60, "confidence": 0.55},
        {"name": "粉/面/主食类", "category": "carbs", "estimated_weight_g": 60, "calories": 120, "confidence": 0.35},
        {"name": "调料/油脂", "category": "sauce_oil", "estimated_weight_g": None, "calories": 100, "confidence": 0.35},
    ],
    "沙拉": [
        {"name": "叶菜基底", "category": "vegetable", "estimated_weight_g": 200, "calories": 60, "confidence": 0.6},
        {"name": "蛋白质类", "category": "protein", "estimated_weight_g": 80, "calories": 120, "confidence": 0.45},
        {"name": "碳水类", "category": "carbs", "estimated_weight_g": 50, "calories": 100, "confidence": 0.4},
        {"name": "酱汁", "category": "sauce_oil", "estimated_weight_g": 30, "calories": 60, "confidence": 0.4},
    ],
    "炒饭": [
        {"name": "米饭", "category": "carbs", "estimated_weight_g": 250, "calories": 290, "confidence": 0.6},
        {"name": "鸡蛋", "category": "protein", "estimated_weight_g": 50, "calories": 78, "confidence": 0.55},
        {"name": "蔬菜丁", "category": "vegetable", "estimated_weight_g": 30, "calories": 10, "confidence": 0.4},
        {"name": "食用油", "category": "sauce_oil", "estimated_weight_g": 15, "calories": 135, "confidence": 0.5},
    ],
    "盖饭": [
        {"name": "米饭", "category": "carbs", "estimated_weight_g": 200, "calories": 230, "confidence": 0.6},
        {"name": "主菜/浇头", "category": "protein", "estimated_weight_g": 150, "calories": 220, "confidence": 0.5},
        {"name": "蔬菜", "category": "vegetable", "estimated_weight_g": 50, "calories": 15, "confidence": 0.4},
        {"name": "酱汁", "category": "sauce_oil", "estimated_weight_g": 30, "calories": 55, "confidence": 0.4},
    ],
}

_GENERIC_FALLBACK: list[dict] = [
    {"name": "主食/碳水类", "category": "carbs", "estimated_weight_g": 150, "calories": 220, "confidence": 0.3},
    {"name": "蛋白质类", "category": "protein", "estimated_weight_g": 100, "calories": 170, "confidence": 0.3},
    {"name": "蔬菜类", "category": "vegetable", "estimated_weight_g": 120, "calories": 40, "confidence": 0.35},
    {"name": "油脂/酱料", "category": "sauce_oil", "estimated_weight_g": None, "calories": 80, "confidence": 0.3},
]


def _match_template(food_name: str) -> list[dict] | None:
    """根据菜品名称匹配已知模板"""
    for key, template in _FALLBACK_TEMPLATES.items():
        if key in food_name:
            return template
    return None


def _normalize_components_to_main_dish(
    components: list[FoodComponent],
    main_weight_g: float,
    main_calories: float,
) -> list[FoodComponent]:
    """确保 fallback components 标记为 include_in_total。

    dish_with_components 模式下，components 的加总即主菜总量，
    不再需要"其他估计"补差。
    """
    for c in components:
        c.include_in_total = True
    return components


def generate_fallback_components(
    food_name: str,
    main_weight_g: float = 0,
    main_calories: float = 0,
) -> list[FoodComponent]:
    """为 whole_dish 菜品生成 fallback components。

    如果匹配到已知模板则使用模板，否则使用通用模板。
    自动归一化到主菜总量范围内。
    """
    template = _match_template(food_name)
    if template is None:
        logger.info("food_component_fallback: no template for %s, using generic", food_name)
        template = _GENERIC_FALLBACK

    components = [
        FoodComponent(
            name=t["name"],
            category=t.get("category", "unknown"),
            estimated_weight_g=t.get("estimated_weight_g"),
            calories=t.get("calories"),
            protein=t.get("protein"),
            carbs=t.get("carbs"),
            fat=t.get("fat"),
            confidence=t.get("confidence", 0.3),
            role=t.get("role", "ingredient"),
            include_in_total=False,
        )
        for t in template
    ]

    # Tag source
    for c in components:
        c.include_in_total = False  # safety: never count twice

    components = _normalize_components_to_main_dish(components, main_weight_g, main_calories)

    logger.info(
        "food_component_fallback: generated %d components for %s (weight=%.0fg, cal=%.0f)",
        len(components), food_name, main_weight_g, main_calories,
    )
    return components
