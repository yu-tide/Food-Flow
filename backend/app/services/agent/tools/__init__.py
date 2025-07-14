"""MCP 工具中心 — 所有工具由 ToolRegistry 统一管理

必须先 import 各工具模块，触发 @ToolRegistry.register 装饰器注册。
"""

# 导出注册表
from app.services.agent.tools.registry import ToolRegistry, ToolSpec, ToolResult, ToolCallRecord

# 导入工具模块（触发装饰器注册）
import app.services.agent.tools.nutrition_tool  # noqa: F401, E402
import app.services.agent.tools.record_tool     # noqa: F401, E402
import app.services.agent.tools.knowledge_tool  # noqa: F401, E402
import app.services.agent.tools.calculator_tool # noqa: F401, E402
import app.services.agent.tools.memory_tool     # noqa: F401, E402

__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "ToolResult",
    "ToolCallRecord",
]
