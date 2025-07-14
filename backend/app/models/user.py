import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    nickname = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    avatar_text = Column(String(10), default="")

    target_calories = Column(Integer, default=2000)
    target_protein = Column(Integer, nullable=True)
    target_carbs = Column(Integer, nullable=True)
    target_fat = Column(Integer, nullable=True)
    goal_type = Column(String(20), default="maintain")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    settings = relationship("UserSettings", back_populates="user", uselist=False)
