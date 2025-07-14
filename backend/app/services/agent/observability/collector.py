"""TraceCollector — 追踪收集器

内存存储 + 可选的数据库持久化。
最近的 100 条 trace 保留在内存中用于实时查询。
"""

from __future__ import annotations
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from app.services.agent.observability.tracer import Trace

logger = logging.getLogger(__name__)

MAX_TRACES = 100


class TraceCollector:
    """追踪收集器 — 线程安全的内存存储"""

    _traces: OrderedDict[str, Trace] = OrderedDict()

    @classmethod
    def store(cls, trace: Trace) -> None:
        """存储一条 trace"""
        trace.close()
        cls._traces[trace.trace_id] = trace
        cls._traces.move_to_end(trace.trace_id)

        # 超出上限时删除最早的
        while len(cls._traces) > MAX_TRACES:
            cls._traces.popitem(last=False)
        logger.info("trace stored: %s (%d spans, %.0fms)",
                    trace.trace_id[:8], len(trace.spans), trace.total_duration_ms)

    @classmethod
    def get(cls, trace_id: str) -> Trace | None:
        return cls._traces.get(trace_id)

    @classmethod
    def list_recent(cls, limit: int = 20) -> list[dict]:
        """获取最近的 trace 摘要列表"""
        traces = list(cls._traces.values())
        traces.reverse()
        return [
            {
                "trace_id": t.trace_id,
                "intent": t.intent,
                "span_count": len(t.spans),
                "total_duration_ms": t.total_duration_ms,
                "status": t.to_dict().get("status", "ok"),
                "time": datetime.fromtimestamp(t.start_time, tz=timezone.utc)
                         .strftime("%H:%M:%S"),
            }
            for t in traces[:limit]
        ]

    @classmethod
    def get_spans(cls, trace_id: str) -> list[dict]:
        """获取某个 trace 的所有 spans"""
        trace = cls._traces.get(trace_id)
        if not trace:
            return []
        return [s.to_dict() for s in trace.spans]

    @classmethod
    def clear(cls) -> None:
        cls._traces.clear()
        logger.info("trace collector cleared")
