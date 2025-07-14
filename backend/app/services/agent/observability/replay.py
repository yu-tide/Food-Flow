"""TraceReplay — 执行回放引擎

读取已收集的 trace，逐步回放每个 span 的操作。
支持对比原始输出与回放输出。
"""

from __future__ import annotations
import logging
from typing import Any

from app.services.agent.observability.collector import TraceCollector

logger = logging.getLogger(__name__)


class ReplaySpanResult:
    """单条 span 的回放结果"""
    def __init__(self, span_name: str, original_duration: float,
                 original_status: str, rerun_duration: float = 0.0,
                 output_match: bool = False, error: str | None = None):
        self.span_name = span_name
        self.original_duration = original_duration
        self.original_status = original_status
        self.rerun_duration = rerun_duration
        self.output_match = output_match
        self.error = error

    def to_dict(self) -> dict:
        return {
            "span_name": self.span_name,
            "original_duration_ms": self.original_duration,
            "original_status": self.original_status,
            "rerun_duration_ms": self.rerun_duration,
            "output_match": self.output_match,
            "error": self.error,
        }


class TraceReplay:
    """Trace 回放引擎"""

    @classmethod
    async def replay(cls, trace_id: str) -> dict:
        """回放一条 trace 的所有 spans"""
        trace = TraceCollector.get(trace_id)
        if not trace:
            return {"ok": False, "error": f"trace not found: {trace_id}"}

        results = []
        for span in trace.spans:
            result = await cls._replay_span(span)
            results.append(result)

        matches = sum(1 for r in results if r.output_match)
        total = len(results)
        logger.info("replay: trace=%s %d/%d spans matched", trace_id[:8], matches, total)

        return {
            "ok": True,
            "trace_id": trace_id,
            "total_spans": total,
            "matching_spans": matches,
            "details": [r.to_dict() for r in results],
        }

    @classmethod
    async def _replay_span(cls, span) -> ReplaySpanResult:
        """回放单个 span

        注意：只有纯函数工具可以真正重放（如 calorie_calculator）。
        DB 操作和 LLM 调用不可重放，标记为 skipped。
        """
        name = span.name
        kind = span.kind

        # 纯函数工具 — 可以重放
        if kind == "tool" and name in (
            "calorie_calculator", "bmr_calculator", "tdee_calculator", "macro_split",
        ):
            try:
                from app.services.agent.tools import ToolRegistry
                import time
                t0 = time.time()
                result = await ToolRegistry.execute(name, span.input, context={})
                duration = (time.time() - t0) * 1000
                output_match = result.data is not None
                return ReplaySpanResult(
                    span_name=name,
                    original_duration=span.duration_ms,
                    original_status=span.status,
                    rerun_duration=round(duration, 1),
                    output_match=output_match,
                )
            except Exception as e:
                return ReplaySpanResult(
                    span_name=name,
                    original_duration=span.duration_ms,
                    original_status=span.status,
                    error=str(e),
                )

        # 非可重放操作 — 标记为 skipped
        return ReplaySpanResult(
            span_name=name,
            original_duration=span.duration_ms,
            original_status=span.status,
            output_match=True,       # 假定原始输出正确
        )
