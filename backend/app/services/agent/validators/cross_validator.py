"""Cross Validator — 跨步骤校验 + 历史对比"""

from __future__ import annotations
import logging
from typing import Any

from app.services.agent.models import ReflectionIssue

logger = logging.getLogger(__name__)


def validate_against_history(
    item: dict,
    history: list[dict],
) -> list[ReflectionIssue]:
    """将当前营养估算与用户历史记录对比

    Args:
        item: 当前估算 {food_name, calories, protein, carbs, fat}
        history: 历史记录列表，每项同格式

    Returns: 发现的异常列表
    """
    issues = []
    if not history:
        return issues

    name = item.get("food_name", "?") or "?"
    cal = _f(item.get("calories"))

    if cal <= 0:
        return issues

    # 1. 热量异常（与历史均值对比）
    cal_values = [_f(h.get("calories")) for h in history if _f(h.get("calories")) > 0]
    if len(cal_values) >= 3:
        mean = sum(cal_values) / len(cal_values)
        std = (sum((x - mean) ** 2 for x in cal_values) / len(cal_values)) ** 0.5

        if std > 0 and abs(cal - mean) > 2.5 * std:
            issues.append(ReflectionIssue(
                issue_type="historical_anomaly", item=name,
                detail=f"当前 {cal:.0f}kcal 与历史均值 {mean:.0f}±{std:.0f}kcal 偏差超过 2.5σ",
                severity="warning",
            ))
        elif std > 0 and abs(cal - mean) > 1.5 * std:
            issues.append(ReflectionIssue(
                issue_type="historical_variance", item=name,
                detail=f"当前 {cal:.0f}kcal 与历史均值 {mean:.0f}±{std:.0f}kcal 偏差超过 1.5σ",
                severity="info",
            ))

    return issues


def validate_cross_step(
    food_estimate: dict,
    record_detail: dict | None = None,
) -> list[ReflectionIssue]:
    """校验不同 Agent 输出之间的一致性"""
    issues = []
    if not record_detail:
        return issues

    est_cal = _f(food_estimate.get("calories"))
    rec_cal = _f(record_detail.get("calories"))
    name = food_estimate.get("food_name", record_detail.get("name", "?"))

    if est_cal > 0 and rec_cal > 0:
        ratio = abs(est_cal - rec_cal) / max(est_cal, rec_cal)
        if ratio > 0.3:
            issues.append(ReflectionIssue(
                issue_type="cross_step_mismatch", item=name,
                detail=f"估算 {est_cal:.0f}kcal 与记录 {rec_cal:.0f}kcal 差异 {ratio:.0%}",
                severity="warning",
            ))

    return issues


def validate_meal_balance(meals: list[dict], target: float = 2000) -> list[ReflectionIssue]:
    """校验一整天各餐的热量分布是否合理"""
    issues = []
    if len(meals) <= 1:
        return issues

    total = sum(_f(m.get("calories")) for m in meals)
    if total <= 0:
        return issues

    # 检查某一餐占比是否异常
    for meal in meals:
        cal = _f(meal.get("calories"))
        name = meal.get("meal_type", meal.get("name", "?"))
        if total > 0 and cal / total > 0.7:
            issues.append(ReflectionIssue(
                issue_type="unbalanced_meal", item=name,
                detail=f"{name} 占总热量 {cal / total:.0%}，建议分散摄入",
                severity="warning",
            ))

    # 检查是否严重超标
    if total > target * 1.5:
        issues.append(ReflectionIssue(
            issue_type="daily_over_target", item="全天",
            detail=f"总摄入 {total:.0f}kcal 超出目标 {target:.0f}kcal 的 150%",
            severity="warning",
        ))

    return issues


def _f(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default
