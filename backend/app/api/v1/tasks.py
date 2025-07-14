from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.analyze_task import AnalyzeTask
from app.models.task_event import TaskEvent
from app.models.user import User
from app.schemas.tasks import (
    current_step,
    estimate_text,
    status_text,
    TaskActiveResponse,
    TaskDetailResponse,
    TaskEventItem,
    RetryResponse,
)
from app.services.task_service import dispatch_analyze_task, retry_task

router = APIRouter(prefix="/tasks", tags=["任务"])


@router.get("/active")
async def get_active_task(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalyzeTask)
        .where(
            AnalyzeTask.user_id == current_user.id,
            AnalyzeTask.status.notin_(["SUCCESS", "FAILED"]),
        )
        .order_by(AnalyzeTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()

    if task is None:
        return None

    return TaskActiveResponse(
        id=str(task.id),
        filename=task.filename,
        status=task.status,
        statusText=status_text(task.status),
        estimateText=estimate_text(task.status, task.eta_seconds),
        currentStep=current_step(task.status),
    )


@router.get("/{task_id}")
async def get_task_detail(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalyzeTask).where(AnalyzeTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if task is None or str(task.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    events_result = await db.execute(
        select(TaskEvent)
        .where(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.created_at.asc())
    )
    events = events_result.scalars().all()

    # 非食物检测：查关联 record 是否为空
    is_food_detected = True
    non_food_reason = None
    if task.record_id:
        from app.models.food_item import FoodItem
        item_count = await db.execute(
            select(FoodItem).where(FoodItem.record_id == task.record_id)
        )
        items_list = item_count.scalars().all()
        if not items_list and task.status == "SUCCESS":
            is_food_detected = False
            non_food_reason = "未识别到可分析的食物"
    elif task.status == "SUCCESS":
        is_food_detected = None

    return TaskDetailResponse(
        id=str(task.id),
        task_id=str(task.id),
        filename=task.filename,
        image_url=task.image_url,
        upload_time=task.upload_time,
        file_size=task.file_size,
        image_format=task.image_format,
        status=task.status,
        progress_percent=task.progress_percent,
        eta_seconds=task.eta_seconds,
        retry_count=task.retry_count,
        error_message=task.error_message,
        record_id=str(task.record_id) if task.record_id else None,
        is_food_detected=is_food_detected,
        non_food_reason=non_food_reason,
        events=[TaskEventItem(time=e.time, title=e.title, created_at=e.created_at) for e in events],
    )


@router.post("/{task_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_task_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalyzeTask).where(AnalyzeTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if task is None or str(task.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    await retry_task(db, task)

    dispatch_analyze_task(task_id=str(task.id), meal_type="", remark="")

    return RetryResponse(message="重试任务已提交")
