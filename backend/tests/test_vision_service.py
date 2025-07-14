"""Vision Service 测试 — mock 模式"""
import pytest
from app.services.vision_service import (
    MOCK_VISION_ITEMS,
    VisionFoodItem,
    VisionResult,
    recognize_food_from_image,
)


@pytest.fixture(autouse=True)
def _force_mock():
    from app.core.config import settings
    old = settings.VISION_MODE
    settings.VISION_MODE = "mock"
    yield
    settings.VISION_MODE = old


class TestMockVision:
    def test_returns_3_items(self):
        r = recognize_food_from_image("/nonexistent.jpg")
        assert r.success is True
        assert r.engine == "vision-mock"
        assert len(r.items) == 3

    def test_item_structure(self):
        r = recognize_food_from_image("/nonexistent.jpg")
        item = r.items[0]
        assert item.food_name == "米饭"
        assert "150" in item.estimated_weight
        assert item.weight_g == 150
        assert item.category == "grain"
        assert item.confidence > 0.7
        assert item.source == "vision"

    def test_all_items_have_food_name(self):
        r = recognize_food_from_image("/nonexistent.jpg")
        for item in r.items:
            assert item.food_name
            assert item.category in ("grain", "protein", "vegetable")

    def test_confidence_in_range(self):
        r = recognize_food_from_image("/nonexistent.jpg")
        for item in r.items:
            assert 0 <= item.confidence <= 1

    def test_mock_constant_stable(self):
        assert len(MOCK_VISION_ITEMS) == 3
        assert MOCK_VISION_ITEMS[0].food_name == "米饭"


class TestVisionResultType:
    def test_vision_result_fields(self):
        r = recognize_food_from_image("/nonexistent.jpg")
        assert isinstance(r, VisionResult)
        assert isinstance(r.items, list)
        assert isinstance(r.engine, str)
        assert isinstance(r.success, bool)
