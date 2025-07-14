"""Agent Memory — lightweight user preferences and behavior patterns for the AI assistant.

Stores structured, time-decaying inferences and explicit user preferences.
Does NOT store raw prompts, medical diagnoses, or sensitive personal data.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base

ALLOWED_MEMORY_TYPES = {"food_preference", "behavior_pattern", "assistant_note", "action_history"}
ALLOWED_SOURCES = {"user_explicit", "inferred_from_records", "action_result"}


class AssistantMemory(Base):
    __tablename__ = "assistant_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    memory_type = Column(String(30), nullable=False)    # food_preference, behavior_pattern, assistant_note, action_history
    key = Column(String(100), nullable=False)            # e.g. "spicy_hotpot_like_frequency", "avoid_foods_mirror"
    value_json = Column(JSONB, nullable=False, default=dict)
    confidence = Column(Float, nullable=False, default=1.0)
    source = Column(String(30), nullable=False)          # user_explicit, inferred_from_records, action_result
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "memory_type", "key", name="uq_user_memory_type_key"),
    )
