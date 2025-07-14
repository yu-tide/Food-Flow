"""Agent 系统 — 多智能体架构 + MCP 工具中心 + 记忆管理 + 可观测性

使用方式：
    from app.services.agent import AgentOrchestrator, ToolRegistry, MemoryManager
    from app.services.agent import Tracer, TraceCollector

    orch = AgentOrchestrator(db, user_id)
    result = await orch.run(message="我今天还能吃什么？")

    # 查看追踪
    traces = TraceCollector.list_recent()
"""

from app.services.agent.orchestrator import AgentOrchestrator
from app.services.agent.models import (
    AgentKind, AgentStep, ExecutionPlan, IntentResult,
    ReflectionResult, ValidationResult, StepStatus,
)
from app.services.agent.tools import ToolRegistry, ToolSpec, ToolResult
from app.services.agent.memory import MemoryManager
from app.services.agent.observability import Tracer, TraceCollector

__all__ = [
    "AgentOrchestrator",
    "AgentKind", "AgentStep", "ExecutionPlan", "IntentResult",
    "ReflectionResult", "ValidationResult", "StepStatus",
    "ToolRegistry", "ToolSpec", "ToolResult",
    "MemoryManager",
    "Tracer", "TraceCollector",
]
