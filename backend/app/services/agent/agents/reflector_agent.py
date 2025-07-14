"""Reflector Agent — 自我反思与质量评估（使用 validators 模块）

流程：
  1. 校验规则引擎（validate_item / validate_items）
  2. 历史对比（validate_against_history）
  3. 质量评分（score_nutrition_quality）
  4. 自动修正（try_correct）
  5. 决策（accept / retry / ask_user）
"""

from __future__ import annotations
import logging

from app.services.agent.agents.base import BaseAgent
from app.services.agent.models import AgentKind, AgentStep, ReflectionIssue, ReflectionResult
from app.services.agent.validators import (
    validate_item, validate_items,
    score_nutrition_quality, QualityLevel,
    validate_against_history,
    try_correct, Correction,
)

logger = logging.getLogger(__name__)


class ReflectorAgent(BaseAgent):
    """反思器：对上一步 Agent 的输出进行多维度质量评估"""

    @property
    def kind(self) -> AgentKind:
        return AgentKind.REFLECTOR

    async def _run(self, step: AgentStep) -> AgentStep:
        ctx = step.input or {}
        prev_output = ctx.get("previous_step_output", {})

        if not prev_output:
            step.complete({
                "reflection": ReflectionResult(passed=True).model_dump(),
                "quality_score": None,
                "corrections": [],
            })
            return step

        issues: list[ReflectionIssue] = []
        quality_result = None
        corrections: list[dict] = []
        corrected_output = dict(prev_output)

        # 1. 校验规则引擎
        if "food_estimate" in prev_output:
            item = prev_output.get("food_estimate", {})
            issues += validate_item(item)

        if "record_detail" in prev_output:
            item = prev_output.get("record_detail", {})
            food_items = item.get("components", [])
            for fi in food_items:
                issues += validate_item(fi)
            if food_items:
                issues += validate_items(food_items)

        if "dashboard_summary" in prev_output:
            dash = prev_output.get("dashboard_summary", {})
            if dash.get("record_count", 0) > 0:
                consumed = dash.get("consumed_calories", 0)
                target = dash.get("target_calories", 2000)
                if consumed > target * 1.5:
                    issues.append(ReflectionIssue(
                        issue_type="over_consumption", item="全天",
                        detail=f"今日摄入 {consumed}kcal 超过目标 {target}kcal 的 150%",
                        severity="warning",
                    ))

        # 2. 历史对比
        history = ctx.get("history_records", [])
        if history and "food_estimate" in prev_output:
            hist_issues = validate_against_history(
                prev_output.get("food_estimate", {}), history,
            )
            issues += hist_issues

        # 3. 质量评分
        if "food_estimate" in prev_output:
            quality_result = score_nutrition_quality(
                prev_output.get("food_estimate", {})
            )
            if quality_result.level in (QualityLevel.POOR, QualityLevel.UNACCEPTABLE):
                issues.append(ReflectionIssue(
                    issue_type="low_quality", item="",
                    detail=f"质量评分: {quality_result.level.value} ({quality_result.score})",
                    severity="error" if quality_result.level == QualityLevel.UNACCEPTABLE else "warning",
                ))

        # 4. 自动修正
        if issues and "food_estimate" in prev_output:
            item = prev_output.get("food_estimate", {})
            corrected_item, applied = try_correct(item, issues)
            if applied:
                corrected_output["food_estimate"] = corrected_item
                corrections = [{"field": c.field, "old": c.old, "new": c.new, "reason": c.reason}
                               for c in applied]
                logger.info("reflector: %d corrections for %s",
                            len(corrections), item.get("food_name", "?"))

        # 5. 决策
        severe = [i for i in issues if i.severity == "error"]
        action = "retry" if severe else "accept"
        if corrections:
            action = "retry"              # 有修正时重新执行
        elif not severe and issues and quality_result and quality_result.level == QualityLevel.FAIR:
            action = "ask_user"

        result = ReflectionResult(
            passed=len(severe) == 0,
            issues=issues,
            action=action,
            revised_output=corrected_output if corrections else None,
        )

        step.complete({
            "reflection": result.model_dump(),
            "quality_score": quality_result.model_dump() if quality_result else None,
            "corrections": corrections,
        })
        return step
