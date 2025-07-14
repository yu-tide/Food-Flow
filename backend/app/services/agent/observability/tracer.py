"""Tracer — 智能体可观测性追踪内核

基于 ContextVar 的上下文追踪，不依赖 OpenTelemetry SDK。
支持嵌套 Span，自动记录耗时和状态。
"""

from __future__ import annotations
import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """单个操作跨度 — 最小可观测单元"""
    span_id: str
    trace_id: str
    parent_id: str | None
    name: str                           # "agent.planner" | "tool.nutrition_retrieve"
    kind: str                           # "agent" | "tool" | "memory" | "llm" | "orchestrator"
    input: dict = field(default_factory=dict)
    output: dict | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"                  # "ok" | "error" | "timeout"
    error: str | None = None
    tags: dict = field(default_factory=dict)

    def close(self):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 1)

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "tags": self.tags,
        }


@dataclass
class Trace:
    """完整执行追踪 — 包含所有 Span"""
    trace_id: str
    session_id: str = ""
    user_id: str = ""
    intent: str = ""
    spans: list[Span] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    total_duration_ms: float = 0.0

    def close(self):
        self.end_time = time.time()
        self.total_duration_ms = round((self.end_time - self.start_time) * 1000, 1)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id[:8] + "..." if self.user_id else "",
            "intent": self.intent,
            "total_duration_ms": self.total_duration_ms,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
            "status": "error" if any(s.status == "error" for s in self.spans) else "ok",
        }


_current_trace: ContextVar[Trace | None] = ContextVar("agent_trace", default=None)


class SpanContext:
    """异步上下文管理器 — with Tracer.span(...) as span:"""

    def __init__(self, name: str, kind: str, input: dict | None = None,
                 tags: dict | None = None):
        self.name = name
        self.kind = kind
        self.input = input or {}
        self.tags = tags or {}
        self.span: Span | None = None

    async def __aenter__(self):
        trace = _current_trace.get()
        if trace is not None:
            parent_id = trace.spans[-1].span_id if trace.spans else None
            self.span = Span(
                span_id=uuid.uuid4().hex[:8],
                trace_id=trace.trace_id,
                parent_id=parent_id,
                name=self.name,
                kind=self.kind,
                input=self.input,
                tags=self.tags,
                start_time=time.time(),
            )
            trace.spans.append(self.span)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_val:
                self.span.status = "error"
                self.span.error = f"{type(exc_val).__name__}: {exc_val}"
            self.span.close()


class Tracer:
    """追踪器 — 管理 Trace 生命周期"""

    @classmethod
    def start_trace(cls, trace_id: str, session_id: str = "",
                    user_id: str = "") -> Trace:
        trace = Trace(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            start_time=time.time(),
        )
        _current_trace.set(trace)
        return trace

    @classmethod
    def current_trace(cls) -> Trace | None:
        return _current_trace.get()

    @classmethod
    def clear(cls):
        _current_trace.set(None)

    @classmethod
    def span(cls, name: str, kind: str, input: dict | None = None,
             tags: dict | None = None) -> SpanContext:
        """创建 Span 上下文管理器

        用法：
            async with Tracer.span("agent.planner", "agent") as ctx:
                ...
        """
        return SpanContext(name=name, kind=kind, input=input, tags=tags)
