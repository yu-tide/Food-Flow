from datetime import datetime
from typing import Optional

from pydantic import BaseModel

STATUS_TEXT_MAP = {
    "PENDING": "等待处理",
    "UPLOADED": "图片上传完成",
    "OCR_PROCESSING": "正在识别图片内容",
    "OCR_SUCCESS": "图片识别完成",
    "STRUCTURING": "正在整理食物信息",
    "CALCULATING": "正在计算营养素",
    "AI_SUMMARIZING": "正在生成饮食建议",
    "SUCCESS": "分析完成",
    "FAILED": "分析失败",
}

_CURRENT_STEP_MAP = {
    "PENDING": 0,
    "UPLOADED": 0,
    "OCR_PROCESSING": 1,
    "OCR_SUCCESS": 1,
    "STRUCTURING": 2,
    "CALCULATING": 3,
    "AI_SUMMARIZING": 4,
    "SUCCESS": 4,
    "FAILED": 4,
}


def status_text(status: str) -> str:
    return STATUS_TEXT_MAP.get(status, status)


def current_step(status: str) -> int:
    return _CURRENT_STEP_MAP.get(status, 0)


def estimate_text(status: str, eta_seconds: int | None) -> str:
    if status == "SUCCESS":
        return "已完成"
    if status == "FAILED":
        return "分析失败"
    if eta_seconds and eta_seconds > 0:
        return f"预计剩余 {eta_seconds} 秒"
    return "正在处理"


class TaskEventItem(BaseModel):
    time: str
    title: str
    created_at: Optional[datetime] = None


class TaskActiveResponse(BaseModel):
    id: str
    filename: str
    status: str
    statusText: str
    estimateText: str
    currentStep: int


class TaskDetailResponse(BaseModel):
    id: str
    task_id: str
    filename: str
    image_url: Optional[str] = None
    upload_time: Optional[datetime] = None
    file_size: Optional[str] = None
    image_format: Optional[str] = None
    status: str
    progress_percent: int
    eta_seconds: Optional[int] = None
    retry_count: int
    error_message: Optional[str] = None
    record_id: Optional[str] = None
    is_food_detected: Optional[bool] = None
    non_food_reason: Optional[str] = None
    events: list[TaskEventItem] = []


class RetryResponse(BaseModel):
    message: str
