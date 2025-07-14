"""营养估算器 — 多源估算，保证未知食物不为零"""
import logging
from dataclasses import dataclass

from app.schemas.ai_food import NutritionEstimateResult, NutritionReference, RecognizedFoodItem
from app.services.food_normalizer import normalize_food_name
from app.services.nutrition_retriever import retrieve_nutrition_references

logger = logging.getLogger(__name__)

# 类别兜底 (per 100g): (calories, protein, carbs, fat)
_CATEGORY_FALLBACK_PER_100G: dict[str, tuple[float, float, float, float]] = {
    "主食": (150, 4.0, 28.0, 2.0),
    "蛋白质": (180, 22.0, 1.0, 10.0),
    "蔬菜": (35, 2.0, 5.0, 0.5),
    "饮品": (50, 1.5, 8.0, 1.5),
    "混合菜": (160, 9.0, 15.0, 8.0),
    "主食混合菜": (170, 8.0, 22.0, 6.0),
    "零食": (400, 6.0, 50.0, 20.0),
    "含糖饮品": (50, 1.5, 8.0, 1.5),
    "混合套餐": (160, 9.0, 18.0, 7.0),
}


def _vision_has_nutrition(item: RecognizedFoodItem) -> bool:
    """判断 Vision AI 是否已返回完整营养数据"""
    vals = [item.calories, item.protein, item.carbs, item.fat]
    return all(v is not None for v in vals) and sum(vals) > 0


def _estimate_from_references(
    weight_g: float,
    refs: list[NutritionReference],
) -> NutritionEstimateResult | None:
    """从检索参考中加权估算营养"""
    if not refs or weight_g <= 0:
        return None

    best = refs[0]
    vals = [best.calories_per_100g, best.protein_per_100g, best.carbs_per_100g, best.fat_per_100g]
    if not all(v is not None and v >= 0 for v in vals):
        return None

    scale = weight_g / 100.0
    cals, prot, carb, fat = [float(v or 0) * scale for v in vals]
    if cals <= 0:
        return None

    return NutritionEstimateResult(
        calories=round(cals, 1),
        protein=round(prot, 1),
        carbs=round(carb, 1),
        fat=round(fat, 1),
        estimated_weight_g=weight_g,
        confidence=best.confidence,
        source="rag",
        estimated=True,
        reasoning=f"基于{best.name}参考数据，{weight_g:.0f}g 换算" + (f": {best.note}" if best.note else ""),
    )


def _category_fallback(
    weight_g: float,
    category: str,
) -> NutritionEstimateResult:
    """类别兜底估算 — 保证不为零"""
    fb = _CATEGORY_FALLBACK_PER_100G.get(category)
    if not fb:
        fb = _CATEGORY_FALLBACK_PER_100G["混合菜"]

    scale = weight_g / 100.0
    return NutritionEstimateResult(
        calories=round(fb[0] * scale, 1),
        protein=round(fb[1] * scale, 1),
        carbs=round(fb[2] * scale, 1),
        fat=round(fb[3] * scale, 1),
        estimated_weight_g=weight_g,
        confidence=0.25,
        source="fallback",
        estimated=True,
        reasoning=f"使用{category}类别兜底估算，{weight_g:.0f}g",
    )


def _default_weight_by_category(category: str | None, quantity_description: str | None) -> float:
    """根据类别和份量描述推断重量"""
    import re

    desc = (quantity_description or "").lower()

    # 从份量描述提取数字
    m = re.search(r"(\d+)\s*(g|克|ml|毫升|碗|盘|份|杯|瓶)", desc)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit in ("g", "克", "ml", "毫升"):
            return num
        if unit in ("碗", "盘"):
            return num * 250
        if unit in ("份"):
            return num * 300
        if unit in ("杯", "瓶"):
            return num * 250

    if "碗" in desc or "盘" in desc or "份" in desc:
        return 300.0
    if "杯" in desc or "瓶" in desc:
        return 250.0

    # Category-based defaults
    defaults = {
        "主食": 200.0,
        "蛋白质": 150.0,
        "蔬菜": 150.0,
        "饮品": 300.0,
        "混合菜": 300.0,
        "主食混合菜": 300.0,
        "混合套餐": 350.0,
        "零食": 50.0,
        "含糖饮品": 300.0,
    }
    return defaults.get(category or "", 250.0)


def estimate_nutrition(
    item: RecognizedFoodItem,
    ocr_food_name: str | None = None,
) -> NutritionEstimateResult:
    """对单个识别到的食物项进行营养估算。

    策略（按优先级）：
    1. Vision AI 已返回完整营养 → 直接使用
    2. Retriever 参考 + 重量换算
    3. 类别兜底

    硬规则：只要 weight_g > 0，最终 calories 不能为 0。
    """
    food_name = item.food_name or ocr_food_name or "未知食物"
    category = item.category or "混合菜"
    weight_g = item.estimated_weight_g or 0.0

    if weight_g <= 0:
        weight_g = _default_weight_by_category(category, item.quantity_description)

    # Strategy 1: Vision estimates
    if _vision_has_nutrition(item):
        return NutritionEstimateResult(
            calories=float(item.calories or 0),
            protein=float(item.protein or 0),
            carbs=float(item.carbs or 0),
            fat=float(item.fat or 0),
            estimated_weight_g=weight_g,
            confidence=item.confidence,
            source="vision",
            estimated=True,
            reasoning=item.reasoning or "AI Vision 直接估算",
        )

    # Strategy 2: Normalize + retrieve references
    norm = normalize_food_name(food_name, category, None)
    refs = retrieve_nutrition_references(
        food_name=norm["normalized_name"],
        category=norm["category"],
        search_queries=norm["search_queries"],
    )

    result = _estimate_from_references(weight_g, refs)
    if result is not None:
        if item.reasoning:
            result.reasoning = f"{item.reasoning}; {result.reasoning}"
        return result

    # Strategy 3: Category fallback
    result = _category_fallback(weight_g, category)
    return result


# Legacy dataclass for backward compatibility with fusion_service
@dataclass
class NutritionEstimate:
    calories: int = 0
    protein: int = 0
    carbs: int = 0
    fat: int = 0
    estimated: bool = True
    confidence: float = 0.0
    source: str = "fallback"

    @classmethod
    def from_result(cls, r: NutritionEstimateResult) -> "NutritionEstimate":
        return cls(
            calories=int(r.calories),
            protein=int(r.protein),
            carbs=int(r.carbs),
            fat=int(r.fat),
            estimated=r.estimated,
            confidence=r.confidence,
            source=r.source,
        )
