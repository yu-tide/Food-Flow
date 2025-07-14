from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.foods import router as foods_router
from app.api.v1.health import router as health_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.assistant_rag import router as assistant_rag_router
from app.api.v1.settings import router as settings_router
from app.api.v1.statistics import router as statistics_router
from app.api.v1.tasks import router as tasks_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["健康检查"])
api_router.include_router(auth_router, tags=["认证"])
api_router.include_router(dashboard_router, tags=["仪表盘"])
api_router.include_router(foods_router, tags=["食物记录"])
api_router.include_router(statistics_router, tags=["每周统计"])
api_router.include_router(settings_router, tags=["用户设置"])
api_router.include_router(assistant_router, tags=["AI 助手"])
api_router.include_router(assistant_rag_router, tags=["AI 助手 RAG"])
api_router.include_router(tasks_router, tags=["任务"])
from app.services.agent.router import agent_v2_router
api_router.include_router(agent_v2_router)  