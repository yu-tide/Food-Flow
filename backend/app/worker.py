import logging

from celery import Celery
from sqlalchemy.orm import configure_mappers

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "foodflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)

# 显式 import 任务模块，确保 worker 启动时加载所有任务
import app.tasks.analyze_food  # noqa: F401

# 预加载所有 model，确保 Base.metadata 在第一个 asyncio.run() 之前完成注册。
# 否则 SQLAlchemy mapper 会在 lazy import 阶段 throw，导致整个分析流程停止。
import app.models  # noqa: F401

from app.db.base import Base

logger.warning("TRACE_WORKER_MODELS_IMPORTED tables=%s", sorted(Base.metadata.tables.keys()))

configure_mappers()

logger.warning("TRACE_WORKER_MAPPERS_CONFIGURED ok=true")

# celery -A app.worker worker --loglevel=info -P solo
