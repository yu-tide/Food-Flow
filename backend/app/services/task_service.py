import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analyze_task import AnalyzeTask
from app.models.task_event import TaskEvent

logger = logging.getLogger(__name__)


async def create_analyze_task(
    db: AsyncSession,
    *,
    user_id: str,
    filename: str,
    image_url: str,
    file_size: str,
    image_format: str,
) -> AnalyzeTask:
    task = AnalyzeTask(
        user_id=user_id,
        filename=filename,
        image_url=image_url,
        file_size=file_size,
        image_format=image_format,
        status="PENDING",
        progress_percent=0,
        upload_time=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()

    now = datetime.now(timezone.utc).strftime("%H:%M")
    event = TaskEvent(
        task_id=task.id,
        time=now,
        title="图片接收完成",
    )
    db.add(event)

    await db.commit()
    await db.refresh(task)

    return task


def dispatch_analyze_task(task_id: str, meal_type: str, remark: str = "") -> None:
    """将分析任务推送到 Celery。Celery 不可用时仅记录日志，不抛异常。"""
    try:
        from app.tasks.analyze_food import analyze_food_image

        analyze_food_image.delay(task_id=task_id, meal_type=meal_type, remark=remark)
        logger.info("Celery task dispatched: task_id=%s", task_id)
    except Exception as exc:
        logger.warning(
            "Celery 不可用，任务 %s 保持 PENDING 状态: %s", task_id, exc
        )


async def retry_task(db: AsyncSession, task: AnalyzeTask) -> AnalyzeTask:
    now = datetime.now(timezone.utc).strftime("%H:%M")

    task.retry_count += 1
    task.status = "PENDING"
    task.progress_percent = 0
    task.eta_seconds = None
    task.error_message = None

    event = TaskEvent(task_id=task.id, time=now, title="任务已重新提交")
    db.add(event)

    await db.commit()
    await db.refresh(task)
    return task