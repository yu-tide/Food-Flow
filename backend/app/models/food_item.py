import uuid

from sqlalchemy import Boolean, Column, Float, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("food_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    food_name = Column(String(200), nullable=False)
    weight = Column(String(50), default="")
    calories = Column(Integer, default=0)
    protein = Column(Integer, default=0)
    carbs = Column(Integer, default=0)
    fat = Column(Integer, default=0)
    category = Column(String(20), default="unknown")
    confidence = Column(Float, default=0.0, nullable=False)
    source = Column(String(20), default="ocr", nullable=False)
    estimated = Column(Boolean, default=False, nullable=False)
    image_url = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    components = Column(JSONB, default=list, nullable=False, server_default="[]")
    dish_family = Column(String(100), nullable=True)
    alternatives = Column(JSONB, nullable=True)
    user_correction = Column(String(200), nullable=True)
