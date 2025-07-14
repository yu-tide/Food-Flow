"""校验规则中心 — 营养数据校验规则集"""

from __future__ import annotations
import logging
from typing import Any

from app.services.agent.models import ReflectionIssue

logger = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────

CALORIES_MIN = 0
CALORIES_MAX = 3000            # 单食物热量上限
WEIGHT_MIN = 0
WEIGHT_MAX = 2000              # 单食物分量上限
MACRO_TOLERANCE = 0.25         # 宏量营养素推算与标注允许 25% 偏差
CONFIDENCE_LOW = 0.5           # 低置信度阈值
CONFIDENCE_MIN = 0.3           # 最低置信度

# ── 单条校验 ─────────────────────────────────────────

def validate_item(item: dict) -> list[ReflectionIssue]:
    """对单个食物项目执行全量校验"""
    issues = []
    name = item.get("food_name", "?") or "?"
    cal = _f(item.get("calories"))
    pro = _f(item.get("protein"))
    carb = _f(item.get("carbs"))
    fat = _f(item.get("fat"))
    conf = _f(item.get("confidence"), 1.0)
    weight = _f(item.get("estimated_weight_g"), 0)

    # 1. 热量范围
    if cal < CALORIES_MIN:
        issues.append(_issue("negative_calories", name,
                             f"热量为负数: {cal}", "error", "calories=0"))
    elif cal > CALORIES_MAX:
        issues.append(_issue("calories_out_of_range", name,
                             f"热量 {cal}kcal 超过上限 {CALORIES_MAX}kcal", "warning",
                             f"calories={CALORIES_MAX}"))

    # 2. 宏量营养素一致性
    if cal > 0:
        expected = pro * 4 + carb * 4 + fat * 9
        if expected > 0:
            gap = abs(cal - expected)
            ratio = gap / cal
            if ratio > MACRO_TOLERANCE:
                issues.append(_issue("macro_mismatch", name,
                    f"宏量营养素推算 {expected:.0f}kcal 与标注 {cal:.0f}kcal 差异 {ratio:.0%}",
                    "warning"))

    # 3. 缺失宏量营养素
    if cal > 0 and pro == 0 and carb == 0 and fat == 0:
        issues.append(_issue("missing_macros", name,
                             "有热量但宏量营养素全部为 0", "warning"))

    # 4. 负数校验
    for k, v in [("protein", pro), ("carbs", carb), ("fat", fat),
                 ("estimated_weight_g", weight)]:
        if v < 0:
            issues.append(_issue(f"negative_{k}", name,
                                 f"{k} 为负数: {v}", "error", f"{k}=0"))

    # 5. 分量校验
    if weight > WEIGHT_MAX:
        issues.append(_issue("weight_out_of_range", name,
                             f"重量 {weight}g 超过合理上限 {WEIGHT_MAX}g", "warning"))

    # 6. 置信度
    if conf < CONFIDENCE_LOW and cal > 0:
        issues.append(_issue("low_confidence", name,
                             f"置信度 {conf:.1f} 偏低，建议标记 estimated=true", "warning",
                             "estimated=true"))
    if conf < CONFIDENCE_MIN:
        issues.append(_issue("very_low_confidence", name,
                             f"置信度 {conf:.1f} 极低，需人工确认", "error"))

    return issues


def validate_items(items: list[dict]) -> list[ReflectionIssue]:
    """交叉项目校验"""
    issues = []
    if len(items) <= 1:
        return issues

    total_cal = sum(_f(i.get("calories")) for i in items)
    names = [i.get("food_name", "?") for i in items]

    # 单餐总热量异常
    if total_cal > 5000:
        issues.append(_issue("meal_too_high", " | ".join(names),
                             f"本餐总热量 {total_cal}kcal 异常偏高", "warning"))

    # 重复食物
    seen = {}
    for i in items:
        n = i.get("food_name", "")
        if n in seen:
            issues.append(_issue("duplicate_food", n, "同一餐中出现重复食物", "warning"))
        seen[n] = True

    return issues


# ── 帮助函数 ─────────────────────────────────────────

def _f(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _issue(t: str, item: str, detail: str, severity: str = "warning",
           fix: str = "") -> ReflectionIssue:
    return ReflectionIssue(
        issue_type=t, item=item, detail=detail,
        severity=severity, suggested_fix=fix,
    )
