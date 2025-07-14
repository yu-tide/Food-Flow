import uuid

from sqlalchemy import Column, Date, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class WeeklyStatistics(Base):
    __tablename__ = "weekly_statistics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    avg_daily_calories = Column(Integer, default=0)
    total_calories = Column(Integer, default=0)
    protein_target_days = Column(Integer, default=0)
    high_carb_days = Column(Integer, default=0)
    record_count = Column(Integer, default=0)
    average_meals = Column(Float, default=0)
    today_gap = Column(Integer, default=0)
