import uuid

from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class AILog(Base):
    __tablename__ = "ai_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    engine = Column(String(50), nullable=False, default="")
    model = Column(String(50), nullable=False, default="")
    prompt_version = Column(String(50), nullable=False, default="")
    prompt_preview = Column(Text, nullable=True)
    response_preview = Column(Text, nullable=True)
    latency = Column(String(20), nullable=True)
    token_usage = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="success")  # success | fallback | error
    error_message = Column(Text, nullable=True)
    cache_hit = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
