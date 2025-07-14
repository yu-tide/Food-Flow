"""OCR + Vision + Estimator 融合服务"""
import logging
from dataclasses import dataclass, field

from app.services.food_parser import ParseResult
from app.services.nutrition_estimator import NutritionEstimate, estimate_nutrition
from app.services.vision_service import VisionFoodItem, VisionResult

logger = logging.getLogger(__name__)


@dataclass
class FusedFoodItem:
    food_name: str = ""
    weight: str = ""
    category: str = "unknown"
    calories: int = 0
    protein: int = 0
    carbs: int = 0
    fat: int = 0
    confidence: float = 0.0
    source: str = "unknown"       # ocr | vision | fusion | manual
    estimated: bool = True


@dataclass
class FusionResult:
    items: list[FusedFoodItem] = field(default_factory=list)
    source: str = "unknown"
    warning: str = ""


def _ocr_to_fused(parser: ParseResult) -> list[FusedFoodItem]:
    """OCR 解析结果转 fused items"""
    return [
        FusedFoodItem(
            food_name=item.food_name,
            weight=item.weight,
            category=item.category,
            calories=item.calories,
            protein=item.protein,
            carbs=item.carbs,
            fat=item.fat,
            confidence=0.9,
            source="ocr",
            estimated=False,
        )
        for item in parser.items
    ]


def _vision_to_fused(vision: VisionResult) -> list[FusedFoodItem]:
    """Vision 结果 + nutrition_estimator 转 fused items"""
    items = []
    for v in vision.items:
        est = estimate_nutrition(v.food_name, v.weight_g, v.estimated_weight)
        items.append(FusedFoodItem(
            food_name=v.food_name,
            weight=v.estimated_weight or "1份",
            category=v.category,
            calories=est.calories,
            protein=est.protein,
            carbs=est.carbs,
            fat=est.fat,
            confidence=min(v.confidence, est.confidence if est.confidence > 0 else v.confidence),
            source="vision",
            estimated=True,
        ))
    return items


def _merge_items(ocr_items: list[FusedFoodItem], vision_items: list[FusedFoodItem]) -> list[FusedFoodItem]:
    """OCR + Vision 融合"""
    result = []
    for o in ocr_items:
        # 检查是否有同名 vision item
        matched = None
        for v in vision_items:
            if o.food_name == v.food_name or o.food_name in v.food_name or v.food_name in o.food_name:
                matched = v
                break
        if matched:
            # 融合：OCR 优先营养数据，Vision 补充名称/类别
            result.append(FusedFoodItem(
                food_name=o.food_name,
                weight=o.weight or matched.weight,
                category=matched.category if matched.category != "unknown" else o.category,
                calories=o.calories,
                protein=o.protein,
                carbs=o.carbs,
                fat=o.fat,
                confidence=min(o.confidence + 0.05, 1.0),
                source="fusion",
                estimated=False,
            ))
        else:
            result.append(o)
    # 追加 vision 独有的 items
    ocr_names = {it.food_name for it in ocr_items}
    for v in vision_items:
        if v.food_name not in ocr_names and not any(
            v.food_name in o or o in v.food_name for o in ocr_names
        ):
            result.append(v)
    return result


def fuse(
    *,
    ocr_text: str | None = None,
    parser_result: ParseResult | None = None,
    vision_result: VisionResult | None = None,
) -> FusionResult:
    """主入口：融合 OCR + Vision 结果

    Returns:
        FusionResult with unified food_items list
    """
    ocr_ok = parser_result is not None and parser_result.success and parser_result.items
    vision_ok = vision_result is not None and vision_result.success and vision_result.items

    # 场景 1: OCR 成功（有营养数字）→ 优先 OCR
    if ocr_ok and not vision_ok:
        logger.info("fusion: OCR only, items=%d", len(parser_result.items))
        return FusionResult(
            items=_ocr_to_fused(parser_result),
            source="ocr",
        )

    # 场景 2: 仅 Vision 成功
    if vision_ok and not ocr_ok:
        logger.info("fusion: Vision only, items=%d", len(vision_result.items))
        return FusionResult(
            items=_vision_to_fused(vision_result),
            source="vision",
        )

    # 场景 3: 两者都有 → 融合
    if ocr_ok and vision_ok:
        ocr_items = _ocr_to_fused(parser_result)
        vision_items = _vision_to_fused(vision_result)
        merged = _merge_items(ocr_items, vision_items)
        logger.info("fusion: merged, ocr=%d vision=%d → fused=%d",
                    len(ocr_items), len(vision_items), len(merged))
        return FusionResult(
            items=merged,
            source="fusion",
        )

    # 场景 4: 两者都失败
    logger.warning("fusion: both OCR and Vision failed")
    return FusionResult(
        items=[],
        source="none",
        warning="OCR 和 Vision 均未识别到有效食物信息",
    )
