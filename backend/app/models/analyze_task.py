import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class AnalyzeTask(Base):
    __tablename__ = "analyze_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    image_url = Column(Text, nullable=True)
    file_size = Column(String(50), nullable=True)
    image_format = Column(String(10), default="JPG")
    status = Column(String(30), default="PENDING")
    progress_percent = Column(Integer, default=0)
    eta_seconds = Column(Integer, nullable=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("food_records.id", use_alter=True),
        nullable=True,
    )
    upload_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
