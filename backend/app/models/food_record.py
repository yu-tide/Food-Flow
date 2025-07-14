import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class FoodRecord(Base):
    __tablename__ = "food_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("analyze_tasks.id"), nullable=True)
    meal_type = Column(String(20), nullable=False)
    image_url = Column(Text, nullable=True)
    remark = Column(Text, nullable=True)
    ocr_text = Column(Text, nullable=True)
    total_calories = Column(Integer, default=0)
    protein = Column(Integer, default=0)
    carbohydrate = Column(Integer, default=0)
    fat = Column(Integer, default=0)
    target_calories = Column(Integer, default=2000)
    status = Column(String(20), default="draft", nullable=False)
    status_label = Column(String(50), default="分析完成")
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    summary = Column(Text, nullable=True)
    prompt_version = Column(String(50), nullable=True)
    ai_latency = Column(String(20), nullable=True)
    cache_hit = Column(Boolean, default=False)
    analysis_mode = Column(String(20), default="dish_with_components", nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
