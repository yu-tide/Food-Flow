"""Self-Correction — 常见营养数据问题的自动修正引擎"""

from __future__ import annotations
import logging
from typing import Any

from app.services.agent.models import ReflectionIssue

logger = logging.getLogger(__name__)


class Correction:
    """单次修正记录"""
    def __init__(self, field: str, old: Any, new: Any, reason: str):
        self.field = field
        self.old = old
        self.new = new
        self.reason = reason


def try_correct(item: dict, issues: list[ReflectionIssue]) -> tuple[dict, list[Correction]]:
    """尝试自动修正常见问题

    Returns: (corrected_item, corrections_applied)
    """
    corrected = dict(item)
    corrections = []

    for issue in issues:
        fix = issue.suggested_fix

        # 1. negative_* → 置为 0
        if issue.issue_type.startswith("negative_") and fix == f"{issue.issue_type.replace('negative_', '')}=0":
            field = issue.issue_type.replace("negative_", "")
            old = corrected.get(field, 0)
            corrected[field] = 0
            corrections.append(Correction(field, old, 0, "负数自动归零"))

        # 2. low_confidence → estimated=true
        if issue.issue_type == "low_confidence" and fix == "estimated=true":
            corrected["estimated"] = True
            corrections.append(Correction("estimated", item.get("estimated", None), True, "低置信度自动标记"))

        # 3. calories_out_of_range → 裁剪到上限
        if issue.issue_type == "calories_out_of_range":
            corrected["calories"] = 3000
            corrections.append(Correction("calories", item.get("calories"), 3000, "热量过高自动裁剪"))

        # 4. negative_calories → 置 0
        if issue.issue_type == "negative_calories":
            corrected["calories"] = 0
            corrections.append(Correction("calories", item.get("calories"), 0, "负数热量自动归零"))

        # 5. missing_macros → 从热量推算
        if issue.issue_type == "missing_macros":
            cal = _f(corrected.get("calories"))
            if cal > 0:
                # 默认按 40% 碳水 / 30% 蛋白 / 30% 脂肪拆分
                carbs = cal * 0.40 / 4
                protein = cal * 0.30 / 4
                fat = cal * 0.30 / 9
                if not corrected.get("protein"):
                    corrected["protein"] = round(protein, 1)
                    corrections.append(Correction("protein", item.get("protein"), round(protein, 1), "从热量推算蛋白"))
                if not corrected.get("carbs"):
                    corrected["carbs"] = round(carbs, 1)
                    corrections.append(Correction("carbs", item.get("carbs"), round(carbs, 1), "从热量推算碳水"))
                if not corrected.get("fat"):
                    corrected["fat"] = round(fat, 1)
                    corrections.append(Correction("fat", item.get("fat"), round(fat, 1), "从热量推算脂肪"))

    if corrections:
        logger.info("self_correction: %d corrections applied to %s",
                    len(corrections), item.get("food_name", "?"))
    return corrected, corrections


def _f(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default
