"""ToolRegistry — MCP 风格工具注册中心

支持：
- 装饰器注册（@ToolRegistry.register）
- 动态发现（按上下文 + 分类过滤）
- 上下文注入（user_id / db 自动填充）
- 权限校验 + 超时 + 审计追踪
"""

from __future__ import annotations
import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolSpec(BaseModel):
    """工具规格 — 每个工具的标准化接口描述"""
    name: str
    description: str
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    risk_level: Literal["none", "low", "medium", "high"] = "none"
    requires_confirmation: bool = False
    requires_context: list[str] = Field(default_factory=list)
    timeout_seconds: int = 15
    rate_limit: int = 0
    categories: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    """工具执行结果"""
    ok: bool = True
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    requires_confirmation: bool = False


class ToolCallRecord(BaseModel):
    """工具调用记录（用于审计）"""
    tool_name: str
    input: dict
    output: dict | None = None
    user_id: str = ""
    duration_ms: float = 0.0
    status: str = "ok"
    error: str | None = None
    timestamp: str = ""


class ToolRegistry:
    """MCP 风格工具注册表"""

    _tools: dict[str, ToolSpec] = {}
    _handlers: dict[str, Callable] = {}

    @classmethod
    def register(cls, spec: ToolSpec):
        """装饰器：注册工具"""
        def decorator(func: Callable):
            name = spec.name
            cls._tools[name] = spec
            cls._handlers[name] = func

            # 从函数签名自动推断 input_schema
            sig = inspect.signature(func)
            params = {}
            for p_name, p_param in sig.parameters.items():
                if p_name in ("self", "cls"):
                    continue
                param_info = {"type": _type_name(p_param.annotation)}
                if p_param.default is not inspect.Parameter.empty:
                    param_info["default"] = p_param.default
                else:
                    param_info["required"] = True
                params[p_name] = param_info
            cls._tools[name].input_schema = params

            logger.info("tool registered: %s (risk=%s, timeout=%ss)",
                        name, spec.risk_level, spec.timeout_seconds)
            return func
        return decorator

    @classmethod
    def get_spec(cls, name: str) -> ToolSpec | None:
        return cls._tools.get(name)

    @classmethod
    def list_all(cls) -> list[ToolSpec]:
        return list(cls._tools.values())

    @classmethod
    def discover(cls, context: dict | None = None, category: str | None = None) -> list[ToolSpec]:
        """动态发现 — 按上下文和分类过滤"""
        ctx = context or {}
        result = []

        for spec in cls._tools.values():
            # 分类过滤
            if category and category not in spec.categories:
                continue

            # 上下文需求检查
            if spec.requires_context:
                missing = [k for k in spec.requires_context if k not in ctx]
                if missing:
                    continue

            result.append(spec)

        return result

    @classmethod
    async def execute(
        cls,
        name: str,
        input: dict,
        context: dict | None = None,
    ) -> ToolResult:
        """执行工具（权限校验 + 上下文注入 + 超时 + 审计）"""
        t_start = time.time()
        ctx = context or {}

        # 1. 查找工具
        if name not in cls._tools:
            return ToolResult(ok=False, error=f"tool not found: {name}")

        spec = cls._tools[name]
        handler = cls._handlers[name]

        # 2. 权限校验
        if spec.risk_level in ("medium", "high") and not ctx.get("confirmed_by_user"):
            if spec.requires_confirmation:
                return ToolResult(
                    ok=False,
                    error=f"{name} 需要用户确认后才能执行",
                    requires_confirmation=True,
                )

        # 3. 上下文注入
        merged_input = dict(input)
        for ctx_key in spec.requires_context:
            if ctx_key not in merged_input and ctx_key in ctx:
                merged_input[ctx_key] = ctx[ctx_key]

        # 4. 执行（含超时）
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await asyncio.wait_for(
                    handler(**merged_input),
                    timeout=spec.timeout_seconds,
                )
            else:
                result = handler(**merged_input)
        except asyncio.TimeoutError:
            duration = (time.time() - t_start) * 1000
            logger.warning("tool timeout: %s (%.0fms)", name, duration)
            return ToolResult(ok=False, error=f"{name} 执行超时 ({spec.timeout_seconds}s)")
        except Exception as e:
            duration = (time.time() - t_start) * 1000
            logger.exception("tool failed: %s", name)
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")

        duration = (time.time() - t_start) * 1000
        logger.info("tool ok: %s (%.0fms)", name, duration)
        return ToolResult(ok=True, data=result, duration_ms=duration)

    @classmethod
    async def batch_execute(
        cls,
        calls: list[tuple[str, dict]],
        context: dict | None = None,
    ) -> list[ToolResult]:
        """批量执行工具（无依赖时并行）"""
        return [await cls.execute(name, inp, context) for name, inp in calls]


def _type_name(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "any"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)
