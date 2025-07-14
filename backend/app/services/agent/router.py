"""Agent 系统 V2 API 路由 — 挂载到主路由使用

手动添加到 app/api/router.py：
    from app.services.agent.router import agent_v2_router
    api_router.include_router(agent_v2_router)
"""

from __future__ import annotations
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.agent import AgentOrchestrator
from app.services.agent.tools import ToolRegistry

logger = logging.getLogger(__name__)

agent_v2_router = APIRouter(prefix="/assistant/v2", tags=["AI 助手 V2（多智能体）"])


# ── Chat ──────────────────────────────────────────────────

class ChatV2Request(BaseModel):
    message: str
    page: str = ""
    page_context: dict = {}
    session_id: str | None = None


class ChatV2Response(BaseModel):
    answer: str
    intent: str = ""
    session_id: str
    sources: list[dict] = []
    plan_summary: dict = {}


@agent_v2_router.post("/chat", response_model=ChatV2Response)
async def chat_v2(
    body: ChatV2Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """多智能体 Chat"""
    logger.warning("TRACE_V2_CHAT msg=%s page=%s", body.message[:60], body.page)
    orch = AgentOrchestrator(db=db, user_id=str(current_user.id), mode="v2")
    result = await orch.run(message=body.message, page=body.page, page_context=body.page_context)
    return ChatV2Response(
        answer=result.get("answer", ""),
        intent=result.get("intent", ""),
        session_id=body.session_id or str(uuid.uuid4()),
        sources=result.get("sources", []),
        plan_summary=result.get("plan_summary", {}),
    )


@agent_v2_router.post("/chat/stream")
async def chat_v2_stream(
    body: ChatV2Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """多智能体 SSE 流式回复"""
    logger.warning("TRACE_V2_STREAM msg=%s page=%s", body.message[:60], body.page)
    orch = AgentOrchestrator(db=db, user_id=str(current_user.id), mode="v2")
    result = await orch.run(message=body.message, page=body.page, page_context=body.page_context)
    session_id = body.session_id or str(uuid.uuid4())

    def format_sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def event_generator():
        try:
            yield format_sse("message", {"delta": result.get("answer", "")})
            yield format_sse("source", {"sources": result.get("sources", [])})
            yield format_sse("plan", {"plan_summary": result.get("plan_summary", {})})
            yield format_sse("done", {"session_id": session_id})
        except Exception:
            yield format_sse("error", {"message": "AI 助手暂时不可用"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── MCP 工具中心 ───────────────────────────────────────────

class MCPToolExecuteRequest(BaseModel):
    input: dict = {}


@agent_v2_router.get("/mcp/tools")
async def mcp_discover_tools(
    category: str | None = Query(None, description="按分类过滤"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """MCP 动态工具发现

    返回当前上下文中可用的工具列表（含 input_schema / risk_level）。
    支持按 category 过滤：nutrition / record / calculation / knowledge / memory
    """
    context = {
        "db": db,
        "user_id": str(current_user.id),
    }
    tools = ToolRegistry.discover(context=context, category=category)
    return {
        "tools": [t.model_dump() for t in tools],
        "total": len(tools),
        "category": category or "all",
    }


@agent_v2_router.post("/mcp/tools/{tool_name}/execute")
async def mcp_execute_tool(
    tool_name: str,
    body: MCPToolExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行指定的 MCP 工具

    自动注入 db / user_id 等上下文。高风险工具需要 confirmed_by_user=true。
    """
    context = {
        "db": db,
        "user_id": str(current_user.id),
        "confirmed_by_user": True,  # 用户主动调用的 API 端点默认可信
    }

    result = await ToolRegistry.execute(tool_name, body.input, context=context)

    return {
        "ok": result.ok,
        "data": result.data,
        "error": result.error,
        "duration_ms": round(result.duration_ms, 1),
        "tool_name": tool_name,
        "requires_confirmation": result.requires_confirmation,
    }


@agent_v2_router.get("/mcp/tools/{tool_name}")
async def mcp_tool_detail(tool_name: str):
    """获取单个工具的完整规格"""
    spec = ToolRegistry.get_spec(tool_name)
    if not spec:
        return {"ok": False, "error": f"tool not found: {tool_name}"}
    return {"ok": True, "tool": spec.model_dump()}


# ── 可观测性 ─────────────────────────────────────────

@agent_v2_router.get("/observability/traces")
async def obs_list_traces(limit: int = 20):
    """获取最近的 Agent 执行追踪列表"""
    from app.services.agent.observability import TraceCollector
    return {"traces": TraceCollector.list_recent(limit)}


@agent_v2_router.get("/observability/traces/{trace_id}")
async def obs_get_trace(trace_id: str):
    """获取单个追踪的完整详情（含所有 spans）"""
    from app.services.agent.observability import TraceCollector
    trace = TraceCollector.get(trace_id)
    if not trace:
        return {"ok": False, "error": "trace not found"}
    return {"ok": True, "trace": trace.to_dict()}


@agent_v2_router.get("/observability/traces/{trace_id}/spans")
async def obs_get_spans(trace_id: str):
    """获取某个追踪的所有 spans"""
    from app.services.agent.observability import TraceCollector
    spans = TraceCollector.get_spans(trace_id)
    return {"trace_id": trace_id, "spans": spans, "count": len(spans)}


@agent_v2_router.post("/observability/traces/{trace_id}/replay")
async def obs_replay_trace(trace_id: str):
    """回放某次追踪（只支持纯函数工具的重放）"""
    from app.services.agent.observability import TraceReplay
    result = await TraceReplay.replay(trace_id)
    return result

