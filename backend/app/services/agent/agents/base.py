"""Agent 基础类 — 所有 Agent 的模板方法基类"""

from __future__ import annotations
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from app.services.agent.models import AgentKind, AgentStep, ToolCall

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类：模板方法模式 + 可观测性埋点"""

    def __init__(self, db: Any = None, user_id: str = "", context: dict | None = None):
        self.db = db
        self.user_id = user_id
        self.context = context or {}

    @property
    @abstractmethod
    def kind(self) -> AgentKind:
        """子类返回自己的类型"""
        ...

    async def execute(self, step: AgentStep) -> AgentStep:
        """模板方法：开始 → 前置校验 → _run → 后置处理 → 结束"""
        step.start_time = time.time()
        logger.info("agent.%s start step=%s", self.kind.value, step.id)

        if not await self._pre_validate(step):
            step.fail("前置校验失败")
            return step

        try:
            step = await self._run(step)
        except Exception as e:
            logger.exception("agent.%s error step=%s", self.kind.value, step.id)
            step.fail(f"{type(e).__name__}: {e}")
            return step

        step.output = await self._post_process(step.output or {})
        logger.info("agent.%s done step=%s duration=%.0fms",
                    self.kind.value, step.id, step.duration_ms)
        return step

    async def _pre_validate(self, step: AgentStep) -> bool:
        """前置校验：子类可覆盖"""
        return True

    @abstractmethod
    async def _run(self, step: AgentStep) -> AgentStep:
        """核心逻辑：子类实现"""
        ...

    async def _post_process(self, output: dict) -> dict:
        """后置处理：子类可覆盖"""
        return output

    def _track_tool(self, step: AgentStep, name: str, input: dict, output: dict | None = None,
                    error: str | None = None, duration_ms: float = 0.0) -> None:
        """记录工具调用"""
        step.tool_calls.append(ToolCall(
            name=name, input=input, output=output,
            error=error, duration_ms=duration_ms,
            status="error" if error else "ok",
        ))
