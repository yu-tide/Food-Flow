"""Fusion Service 测试"""
from app.services.food_parser import parse_ocr_text
from app.services.fusion_service import fuse
from app.services.vision_service import MOCK_VISION_ITEMS, VisionResult


class TestFusionOcrOnly:
    def test_ocr_nutrition_label(self):
        parser = parse_ocr_text("鸡胸肉饭 热量520 蛋白质36 脂肪12 碳水65")
        r = fuse(parser_result=parser)
        assert r.source == "ocr"
        assert len(r.items) == 1
        item = r.items[0]
        assert item.calories == 520
        assert item.protein == 36
        assert item.source == "ocr"
        assert item.estimated is False
        assert item.confidence > 0.8


class TestFusionVisionOnly:
    def test_vision_food_photo(self):
        vision = VisionResult(items=MOCK_VISION_ITEMS, engine="mock", success=True)
        r = fuse(vision_result=vision)
        assert r.source == "vision"
        assert len(r.items) == 3
        item = r.items[0]
        assert item.food_name == "米饭"
        assert item.source == "vision"
        assert item.estimated is True


class TestFusionBoth:
    def test_ocr_and_vision(self):
        parser = parse_ocr_text("鸡胸肉饭 热量520 蛋白质36 脂肪12 碳水65")
        vision = VisionResult(items=MOCK_VISION_ITEMS, engine="mock", success=True)
        r = fuse(parser_result=parser, vision_result=vision)
        assert r.source == "fusion"
        assert len(r.items) >= 1
        ocr_item = next((it for it in r.items if "fusion" in it.source), None)
        assert ocr_item is not None
        assert ocr_item.calories == 520  # OCR nutrition retained
        assert ocr_item.estimated is False


class TestFusionNone:
    def test_both_fail(self):
        r = fuse()
        assert r.source == "none"
        assert len(r.items) == 0
        assert "未识别" in r.warning
