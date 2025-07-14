"""Quality Scorer — 营养数据质量评分

支持 mock 和 LLM 两种评估模式。
"""

from __future__ import annotations
import logging
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class QualityLevel(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"


class QualityScore(BaseModel):
    """质量评分结果"""
    score: float                             # 0.0 - 1.0
    level: QualityLevel
    issues: list[str] = []
    confidence_ok: bool = True
    completeness_ok: bool = True
    consistency_ok: bool = True
    suggestion: str = ""


def score_nutrition_quality(item: dict) -> QualityScore:
    """评估单个营养数据的质量"""
    cal = _f(item.get("calories"))
    pro = _f(item.get("protein"))
    carb = _f(item.get("carbs"))
    fat = _f(item.get("fat"))
    conf = _f(item.get("confidence"), 1.0)
    estimated = item.get("estimated", True)
    issues = []

    # 成分分数 (0-40)
    has_cal = cal > 0
    has_pro = pro > 0
    has_carb = carb > 0
    has_fat = fat > 0
    macro_count = sum([has_pro, has_carb, has_fat])
    completeness_score = (1.0 if has_cal else 0.0) * 15 + (macro_count / 3) * 25

    # 置信度分数 (0-30)
    confidence_score = min(conf / 1.0 * 30, 30)
    if conf < 0.3:
        issues.append("置信度极低")
    elif conf < 0.6:
        issues.append("置信度偏低")

    # 一致性分数 (0-30)
    consistency_score = 30
    if has_cal and macro_count > 0:
        expected = pro * 4 + carb * 4 + fat * 9
        if expected > 0:
            ratio = abs(cal - expected) / max(cal, expected)
            if ratio > 0.25:
                consistency_score *= max(0, 1 - ratio)
                issues.append("宏量营养素与热量不一致")

    total = completeness_score + confidence_score + consistency_score
    level = _to_level(total, issues)
    completeness_ok = has_cal and macro_count >= 2

    return QualityScore(
        score=round(total / 100, 2),
        level=level,
        issues=issues,
        confidence_ok=conf >= 0.5,
        completeness_ok=completeness_ok,
        consistency_ok=consistency_score > 20,
        suggestion=_suggestion(level, estimated, issues),
    )


def score_confidence(confidence: float) -> QualityLevel:
    """置信度分级"""
    if confidence >= 0.9:
        return QualityLevel.EXCELLENT
    if confidence >= 0.7:
        return QualityLevel.GOOD
    if confidence >= 0.5:
        return QualityLevel.FAIR
    if confidence >= 0.3:
        return QualityLevel.POOR
    return QualityLevel.UNACCEPTABLE


async def llm_quality_assessment(item: dict, context: dict | None = None) -> QualityScore:
    """LLM 质量评估兜底（当规则引擎不确定时）"""
    from app.core.config import settings
    if settings.AI_MODE == "mock":
        return score_nutrition_quality(item)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.BAILIAN_API_KEY, base_url=settings.BAILIAN_BASE_URL)

        prompt = (
            f"评估以下营养数据的质量，返回 score(0-1) 和 issue 列表。\n"
            f"数据: {item}\n"
            f"格式: score=X.X, issues=[...]"
        )
        resp = client.chat.completions.create(
            model=settings.BAILIAN_MODEL,
            messages=[{"role": "user", "content": prompt}],
            timeout=10,
        )
        # 目前 fallback 到规则引擎
        return score_nutrition_quality(item)
    except Exception as e:
        logger.warning("LLM quality assessment failed: %s", e)
        return score_nutrition_quality(item)


# ── 帮助函数 ─────────────────────────────────────────

def _f(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _to_level(score: float, issues: list) -> QualityLevel:
    if score >= 90 and not issues:
        return QualityLevel.EXCELLENT
    if score >= 75:
        return QualityLevel.GOOD
    if score >= 55:
        return QualityLevel.FAIR
    if score >= 35:
        return QualityLevel.POOR
    return QualityLevel.UNACCEPTABLE


def _suggestion(level: QualityLevel, estimated: bool, issues: list) -> str:
    if level == QualityLevel.UNACCEPTABLE:
        return "建议重新分析"
    if level == QualityLevel.POOR:
        return "建议人工确认后再保存"
    if estimated and level == QualityLevel.FAIR:
        return "数据有estimated标记，可接受但需用户注意"
    return ""
