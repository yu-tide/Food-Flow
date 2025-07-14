"""Agent 系统共享数据模型 — 所有 Agent 之间的通信契约"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentKind(str, Enum):
    """Agent 类型枚举"""
    PLANNER = "planner"
    ANALYZER = "analyzer"
    VALIDATOR = "validator"
    REFLECTOR = "reflector"
    MEMORY = "memory"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ToolCall(BaseModel):
    """单次工具调用记录"""
    name: str
    input: dict = Field(default_factory=dict)
    output: dict | None = None
    duration_ms: float = 0.0
    status: str = "ok"
    error: str | None = None


class AgentStep(BaseModel):
    """Agent 执行计划中的单个步骤"""
    id: str = ""
    agent: AgentKind
    description: str = ""
    input: dict = Field(default_factory=dict)
    output: dict | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    error_message: str | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0

    def complete(self, output: dict):
        self.output = output
        self.status = StepStatus.COMPLETED
        self.end_time = __import__("time").time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

    def fail(self, error: str):
        self.status = StepStatus.FAILED
        self.error_message = error
        self.end_time = __import__("time").time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


class ExecutionPlan(BaseModel):
    """Planner Agent 生成的完整执行计划"""
    intent: str
    steps: list[AgentStep] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    max_iterations: int = 3
    current_iteration: int = 0
    created_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.created_at:
            self.created_at = str(
                datetime.now(timezone.utc).isoformat()
            )

    @property
    def is_done(self) -> bool:
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
            for s in self.steps
        ) or self.current_iteration >= self.max_iterations

    @property
    def next_pending_step(self) -> AgentStep | None:
        for s in self.steps:
            if s.status == StepStatus.PENDING:
                return s
        return None


class IntentResult(BaseModel):
    """意图分类结果"""
    intent: str
    confidence: float = 1.0
    requires_user_data: bool = False
    requires_rag: bool = False
    risk_level: Literal["none", "low", "medium", "high"] = "low"
    needs_clarification: bool = False
    clarification_question: str = ""
    entities: list[str] = Field(default_factory=list)
    raw_plan_summary: str = ""


class ReflectionIssue(BaseModel):
    """反思发现的问题"""
    issue_type: str
    item: str = ""
    detail: str = ""
    severity: Literal["info", "warning", "error"] = "warning"
    suggested_fix: str = ""


class ReflectionResult(BaseModel):
    """反思结果"""
    passed: bool = True
    issues: list[ReflectionIssue] = Field(default_factory=list)
    action: Literal["accept", "retry", "ask_user"] = "accept"
    revised_output: dict | None = None


class ValidationResult(BaseModel):
    """校验结果"""
    passed: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
