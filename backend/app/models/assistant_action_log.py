"""Phase 18: Action Audit Log — persistent record of all AI-triggered safe actions."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class AssistantActionLog(Base):
    __tablename__ = "assistant_action_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    action_id = Column(String(100), nullable=True, index=True)
    action_type = Column(String(50), nullable=False, index=True)
    payload_json = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending / success / failed / cancelled
    risk_level = Column(String(20), nullable=False, default="low")
    requires_confirmation = Column(Boolean, nullable=False, default=False)
    result_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    before_snapshot_json = Column(JSONB, nullable=True)
    after_snapshot_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
