"""Unified AI food recognition, nutrition reference, and estimation schemas."""

from pydantic import BaseModel, field_validator


def _clamp_confidence(v: float) -> float:
    return max(0.0, min(1.0, v))


class FoodComponent(BaseModel):
    """A visible ingredient/component of a composite dish, not counted separately."""

    name: str
    confidence: float = 0.5
    estimated_weight_g: float | None = None
    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None
    role: str = "ingredient"  # ingredient | sauce | side | unknown
    include_in_total: bool = False

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return _clamp_confidence(v)


class RecognizedFoodItem(BaseModel):
    """A single food item recognized by AI Vision."""

    food_name: str
    display_name: str | None = None
    category: str | None = None
    estimated_weight_g: float | None = None
    quantity_description: str | None = None

    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None

    confidence: float = 0.5
    source: str = "vision"
    estimated: bool = True
    reasoning: str | None = None
    role: str = "independent"  # main_dish | component | independent
    include_in_total: bool = True
    components: list[FoodComponent] = []
    dish_family: str | None = None
    alternatives: list[dict] = []
    user_correction: str | None = None

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return _clamp_confidence(v)


class FoodImageRecognitionResult(BaseModel):
    """Complete result from AI food recognition of an image."""

    is_food_detected: bool
    analysis_mode: str = "whole_dish"  # whole_dish | component_sum | mixed
    non_food_reason: str | None = None
    scene_description: str | None = None
    confidence: float = 0.5
    food_items: list[RecognizedFoodItem] = []
    warnings: list[str] = []

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return _clamp_confidence(v)


class NutritionReference(BaseModel):
    """A nutrition reference entry retrieved from RAG / knowledge base."""

    name: str
    category: str | None = None
    calories_per_100g: float | None = None
    protein_per_100g: float | None = None
    carbs_per_100g: float | None = None
    fat_per_100g: float | None = None
    source: str = "rag"
    confidence: float = 0.5
    note: str | None = None

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return _clamp_confidence(v)


class NutritionEstimateResult(BaseModel):
    """Final nutrition estimate for a food item, from any source."""

    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    estimated_weight_g: float = 100.0
    confidence: float = 0.5
    source: str = "fallback"
    estimated: bool = True
    reasoning: str | None = None

    @field_validator("calories", "protein", "carbs", "fat", "estimated_weight_g")
    @classmethod
    def clamp_non_negative(cls, v: float) -> float:
        return max(0.0, v)

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return _clamp_confidence(v)
