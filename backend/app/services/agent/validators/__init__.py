"""反思与校验模块 — 统一导出

所有校验规则自动注册，ValidatorAgent 和 ReflectorAgent 共用。
"""

from app.services.agent.validators.nutrition_rules import (
    validate_item, validate_items,
)
from app.services.agent.validators.quality_scorer import (
    QualityScore, QualityLevel,
    score_nutrition_quality, score_confidence,
)
from app.services.agent.validators.self_correction import (
    Correction, try_correct,
)
from app.services.agent.validators.cross_validator import (
    validate_against_history, validate_cross_step, validate_meal_balance,
)

__all__ = [
    "validate_item", "validate_items",
    "QualityScore", "QualityLevel",
    "score_nutrition_quality", "score_confidence",
    "Correction", "try_correct",
    "validate_against_history", "validate_cross_step", "validate_meal_balance",
]
