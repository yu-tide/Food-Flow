import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Body info
    gender = Column(String(10), nullable=True, default="unknown")
    age = Column(Integer, nullable=True)
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    activity_level = Column(String(20), nullable=True, default="light")
    target_weight_kg = Column(Integer, nullable=True)

    # Nutrition targets (mirrored on users for backward compat)
    target_calories = Column(Integer, default=2000)
    target_protein = Column(Integer, nullable=True)
    target_carbs = Column(Integer, nullable=True)
    target_fat = Column(Integer, nullable=True)
    goal_type = Column(String(20), default="maintain")
    nutrition_goal_mode = Column(String(20), default="agent_recommended")

    # Diet preferences
    diet_style = Column(String(20), nullable=True, default="normal")
    taste_preference = Column(String(10), nullable=True, default="normal")
    avoid_foods = Column(Text, nullable=True)
    allergens = Column(Text, nullable=True)
    cuisines = Column(JSONB, nullable=True, default=list, server_default="[]")

    # AI analysis preferences
    ai_recognition_mode = Column(String(20), default="standard")
    ai_estimate_mode = Column(String(20), default="standard")
    ai_low_confidence_confirm = Column(Boolean, default=True)
    ai_show_components = Column(Boolean, default=True)
    ai_show_summary = Column(Boolean, default=True)
    ai_confirm_similar_dish = Column(Boolean, default=True)

    # Notifications
    breakfast_reminder_enabled = Column(Boolean, default=True)
    breakfast_reminder_time = Column(String(5), nullable=True, default="08:30")
    lunch_reminder_enabled = Column(Boolean, default=True)
    lunch_reminder_time = Column(String(5), nullable=True, default="12:00")
    dinner_reminder_enabled = Column(Boolean, default=True)
    dinner_reminder_time = Column(String(5), nullable=True, default="18:30")
    daily_summary_enabled = Column(Boolean, default=True)
    daily_summary_time = Column(String(5), nullable=True, default="21:30")
    weekly_report_enabled = Column(Boolean, default=True)
    weekly_report_day = Column(Integer, nullable=True, default=7)
    weekly_report_time = Column(String(5), nullable=True, default="10:00")
    inactivity_reminder_enabled = Column(Boolean, default=True)

    # Data & privacy
    image_retention_policy = Column(String(20), default="keep_history")
    allow_anonymous_ai_training = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="settings")
