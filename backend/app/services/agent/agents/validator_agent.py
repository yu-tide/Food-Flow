"""Validator Agent — 数据校验与权限校验（使用 validators 模块）"""

from __future__ import annotations
import logging

from app.services.agent.agents.base import BaseAgent
from app.services.agent.models import AgentKind, AgentStep, ValidationResult
from app.services.agent.validators import (
    validate_item, validate_items,
    validate_cross_step, validate_meal_balance,
)

logger = logging.getLogger(__name__)


class ValidatorAgent(BaseAgent):
    """校验器：营养规则引擎 + 交叉校验 + 操作权限校验"""

    @property
    def kind(self) -> AgentKind:
        return AgentKind.VALIDATOR

    async def _run(self, step: AgentStep) -> AgentStep:
        desc = step.description
        ctx = step.input or {}

        if "权限" in desc or "操作" in desc:
            result = self._validate_permission(ctx)
            step.complete({"validation": result.model_dump()})
        elif "交叉" in desc:
            result = self._validate_cross(ctx)
            step.complete({"validation": result.model_dump()})
        else:
            # 默认：营养规则引擎
            result = self._validate_full(ctx)
            step.complete({"validation": result.model_dump()})

        return step

    def _validate_full(self, ctx: dict) -> ValidationResult:
        """全量营养校验"""
        result = ValidationResult()
        food_items = ctx.get("food_items", [])

        for item in food_items:
            issues = validate_item(item)
            for iss in issues:
                msg = f"[{iss.item}] {iss.detail}"
                if iss.severity == "error":
                    result.errors.append(msg)
                else:
                    result.warnings.append(msg)

        if food_items:
            cross_issues = validate_items(food_items)
            for iss in cross_issues:
                result.warnings.append(f"[{iss.item}] {iss.detail}")

        result.passed = len(result.errors) == 0
        return result

    def _validate_cross(self, ctx: dict) -> ValidationResult:
        """交叉校验"""
        result = ValidationResult()

        food_est = ctx.get("food_estimate", {})
        rec_detail = ctx.get("record_detail", {})
        if food_est and rec_detail:
            issues = validate_cross_step(food_est, rec_detail)
            for iss in issues:
                result.warnings.append(f"[{iss.item}] {iss.detail}")

        meals = ctx.get("meals", [])
        target = ctx.get("target_calories", 2000)
        if meals:
            bal_issues = validate_meal_balance(meals, target)
            for iss in bal_issues:
                result.warnings.append(f"[{iss.item}] {iss.detail}")

        result.passed = len(result.errors) == 0
        return result

    def _validate_permission(self, ctx: dict) -> ValidationResult:
        """操作权限校验"""
        result = ValidationResult()
        action = ctx.get("action_type", "")
        risk = ctx.get("risk_level", "low")

        if risk == "high" and not ctx.get("confirmed_by_user"):
            result.errors.append(f"高风险操作 {action} 需要用户确认")

        forbidden_actions = {"delete_all", "clear_all", "auto_confirm_all"}
        if action in forbidden_actions:
            result.errors.append(f"禁止的操作类型: {action}")

        result.passed = len(result.errors) == 0
        return result
