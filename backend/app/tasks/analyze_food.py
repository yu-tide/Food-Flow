import asyncio
import logging

from sqlalchemy import select

from app.worker import celery_app
from app.db.session import async_session
from app.services.food_service import run_mock_analysis, _fail_task, _get_task

logger = logging.getLogger(__name__)


async def _verify_db_connectivity() -> bool:
    """Pre-flight: verify DB is reachable before starting the analysis pipeline."""
    try:
        async with async_session() as db:
            await db.execute(select(1))
        return True
    except Exception as e:
        logger.critical("DB connectivity check failed: %s", e)
        return False


async def _mark_failed_safely(task_id: str, error_message: str) -> bool:
    """Try to mark task as FAILED. Returns False if even this fails."""
    try:
        async with async_session() as db:
            await _fail_task(db, task_id, error_message)
        return True
    except Exception as inner:
        logger.critical("CRITICAL: Cannot mark task %s as FAILED: %s", task_id, inner)
        return False


@celery_app.task(name="analyze_food_image", bind=True, max_retries=3)
def analyze_food_image(self, task_id: str, meal_type: str, remark: str | None = None):
    """AI 分析食物图片的异步任务。

    7 阶段推进并在 SUCCESS 时写入 FoodRecord + FoodItems。
    Celery 不可用时 task_service 端有 try/except 降级保护。
    """
    # Pre-flight: verify DB connectivity before starting the pipeline
    ok = asyncio.run(_verify_db_connectivity())
    if not ok:
        # Mark task FAILED so frontend doesn't hang
        asyncio.run(_mark_failed_safely(task_id, "数据库连接失败，请稍后重试"))
        raise RuntimeError(f"Task {task_id}: DB connectivity check failed")

    try:
        asyncio.run(run_mock_analysis(task_id, meal_type, remark))
    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        asyncio.run(_mark_failed_safely(task_id, str(exc)[:500]))
        raise