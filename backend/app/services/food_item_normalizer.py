"""食物项规范化 — 防止组合菜 parent + components 重复计入热量"""
import logging

from app.schemas.ai_food import FoodComponent, RecognizedFoodItem

logger = logging.getLogger(__name__)


def normalize_food_items(items: list[RecognizedFoodItem], analysis_mode: str = "dish_with_components") -> list[RecognizedFoodItem]:
    """规范化 food_items 根据 analysis_mode。

    dish_with_components: 主菜由 components 汇总得出。main_dish 的 weight/calories 从 components 计算。
    component_sum: 全部作为 independent items，无主项。
    mixed: dish block (components 汇总) + independent items。
    """
    if not items:
        return items

    if analysis_mode == "component_sum":
        for item in items:
            item.role = "independent"
            item.include_in_total = True
        return items

    if analysis_mode in ("dish_with_components", "whole_dish"):
        # Normalize mode name
        analysis_mode = "dish_with_components"
        main_items = [it for it in items if it.role == "main_dish"]
        other_items = [it for it in items if it.role not in ("main_dish",)]

        if not main_items:
            # No main dish — promote all to independent
            for it in items:
                it.role = "independent"
                it.include_in_total = True
            return items

        main = main_items[0]

        # Merge loose other_items into main.components
        if other_items:
            existing = {c.name for c in main.components}
            for other in other_items:
                if other.food_name and other.food_name not in existing:
                    existing.add(other.food_name)
                    main.components.append(FoodComponent(
                        name=other.food_name,
                        confidence=other.confidence,
                        estimated_weight_g=other.estimated_weight_g or 0,
                        calories=other.calories or 0,
                        protein=other.protein,
                        carbs=other.carbs,
                        fat=other.fat,
                        include_in_total=True,
                    ))

        # CORE: derive main_dish totals from components sum
        _derive_dish_from_components(main)
        return [main]

    if analysis_mode == "mixed":
        result = []
        for item in items:
            if item.role == "main_dish":
                # Derive dish totals from its components
                _derive_dish_from_components(item)
                result.append(item)
            elif item.role == "independent":
                item.include_in_total = True
                result.append(item)
            elif item.role == "component":
                # Move stray component to first main_dish
                for it in items:
                    if it.role == "main_dish":
                        it.components.append(FoodComponent(
                            name=item.food_name,
                            confidence=item.confidence,
                            estimated_weight_g=item.estimated_weight_g,
                            calories=item.calories,
                            protein=item.protein,
                            carbs=item.carbs,
                            fat=item.fat,
                            include_in_total=True,
                        ))
                        break
        return result

    return items


def _derive_dish_from_components(main: RecognizedFoodItem) -> None:
    """从 components 汇总计算 main_dish 的 nutrition。

    dish_with_components 模式下，主菜不是一个独立估算的营养实体，
    而是下面 components 的汇总。用户修改 component 后，主菜总量自动变化。
    """
    if not main.components:
        return

    # Only count components marked include_in_total
    included = [c for c in main.components if c.include_in_total]
    if not included:
        # If no components are marked include_in_total, treat all as included
        included = list(main.components)

    total_weight = sum(c.estimated_weight_g or 0 for c in included)
    total_cal = sum(c.calories or 0 for c in included)
    total_pro = sum(c.protein or 0 for c in included)
    total_carbs = sum(c.carbs or 0 for c in included)
    total_fat = sum(c.fat or 0 for c in included)

    old_weight = main.estimated_weight_g
    old_cal = main.calories

    main.estimated_weight_g = round(total_weight, 1) if total_weight > 0 else main.estimated_weight_g
    main.calories = round(total_cal, 1) if total_cal > 0 else main.calories
    main.protein = round(total_pro, 1)
    main.carbs = round(total_carbs, 1)
    main.fat = round(total_fat, 1)

    if old_weight and main.estimated_weight_g and abs(old_weight - main.estimated_weight_g) > 1:
        logger.info("_derive_dish_from_components: %s weight adjusted %.0f -> %.0f",
                     main.food_name, old_weight, main.estimated_weight_g)
    if old_cal and main.calories and abs(old_cal - main.calories) > 1:
        logger.info("_derive_dish_from_components: %s calories adjusted %.0f -> %.0f",
                     main.food_name, old_cal, main.calories)
