from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

MEAL_TYPE_VALUES = Literal["breakfast", "lunch", "dinner", "snack"]
VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
VALID_IMAGE_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}


class FoodUploadResponse(BaseModel):
    task_id: str


class FoodComponentDetail(BaseModel):
    name: str
    confidence: float = 0.5
    estimated_weight_g: Optional[float] = None
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    role: str = "ingredient"
    include_in_total: bool = False


class FoodItemDetail(BaseModel):
    id: str
    food_name: str
    weight: str
    calories: int
    protein: int
    carbohydrate: int  # DB 字段 carbs，API 返回 carbohydrate
    fat: int
    image_url: Optional[str] = None
    category: str = "unknown"
    confidence: float = 0.0
    source: str = "unknown"
    estimated: bool = False
    components: list[FoodComponentDetail] = []


class FoodRecordDetail(BaseModel):
    id: str
    status: str = "draft"
    status_label: str
    confirmed_at: Optional[datetime] = None
    total_calories: int
    protein: int
    carbohydrate: int
    fat: int
    target_calories: int
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    summary: Optional[str] = None
    ocr_text: Optional[str] = None
    is_food_detected: Optional[bool] = None
    non_food_reason: Optional[str] = None


class AiLogDetail(BaseModel):
    prompt_version: Optional[str] = None
    latency: Optional[str] = None
    cache_hit: bool = False


class MacroTargets(BaseModel):
    protein: int
    carbs: int
    fat: int


class MacroPercentages(BaseModel):
    protein: int
    carbs: int
    fat: int


class FoodDetailData(BaseModel):
    record: FoodRecordDetail
    food_items: list[FoodItemDetail]
    ai_log: AiLogDetail
    macro_targets: MacroTargets
    macro_percentages: MacroPercentages


class FoodDetailResponse(BaseModel):
    data: FoodDetailData


class FoodListItemDetail(BaseModel):
    food_name: str


class FoodListItem(BaseModel):
    id: str
    status: str = "draft"
    meal_type: str
    title: str
    time: str
    created_at: Optional[str] = None
    total_calories: int
    summary: Optional[str] = None
    protein: int
    carbohydrate: int
    fat: int
    image_url: Optional[str] = None
    foods: str = ""
    food_items: list[FoodListItemDetail] = []


class FoodListResponse(BaseModel):
    data: list[FoodListItem]


class ConfirmFoodItem(BaseModel):
    id: str
    food_name: str
    weight: str = ""
    category: str = "unknown"
    calories: int = 0
    protein: int = 0
    carbs: int = 0
    fat: int = 0


class DraftFoodItemUpdate(BaseModel):
    """draft update 接受的 item 字段 — 比 ConfirmFoodItem 更宽松"""
    id: str | None = None
    food_name: str | None = None
    display_name: str | None = None
    name: str | None = None
    weight: str | None = None
    estimated_weight_g: float | None = None
    quantity_description: str | None = None
    category: str | None = None
    is_new: bool = False
    name_changed: bool = False


class ConfirmFoodRequest(BaseModel):
    items: list[ConfirmFoodItem]


class ConfirmFoodResponse(BaseModel):
    message: str = "确认成功"
    record_id: str