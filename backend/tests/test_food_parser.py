"""Food Parser 单元测试"""
import pytest
from app.services.food_parser import (
    _classify_food,
    _extract_weight,
    _normalize_text,
    _parse_data_from_text,
    parse_ocr_text,
)


class TestNormalize:
    def test_fullwidth_colon(self):
        assert ":" in _normalize_text("热量：520")

    def test_cjk_comma_to_space(self):
        result = _normalize_text("鸡胸肉饭、热量、520")
        assert "、" not in result
        assert " " in result


class TestParseNutrition:
    def test_standard_format(self):
        item = _parse_data_from_text("热量 520 kcal 蛋白质 36 g 脂肪 12 g 碳水 65 g")
        assert item.calories == 520
        assert item.protein == 36
        assert item.fat == 12
        assert item.carbs == 65

    def test_no_spaces(self):
        item = _parse_data_from_text("热量520kcal 蛋白质36g 脂肪12g 碳水65g")
        assert item.calories == 520
        assert item.protein == 36
        assert item.fat == 12
        assert item.carbs == 65

    def test_fullwidth_delimited(self):
        text = _normalize_text("鸡胸肉饭、热量：520 kcal、蛋白质：36 g、脂肪：12 g、碳水：65 g")
        item = _parse_data_from_text(text)
        assert item.calories == 520
        assert item.protein == 36
        assert item.fat == 12
        assert item.carbs == 65

    def test_all_zero_for_empty(self):
        item = _parse_data_from_text("")
        assert item.calories == 0
        assert item.protein == 0


class TestWeight:
    def test_default_for_nutrition_only(self):
        w = _extract_weight(_normalize_text("热量 520 kcal 蛋白质 36 g 脂肪 12 g 碳水 65 g"))
        assert w == "1份"

    def test_explicit_food_weight(self):
        w = _extract_weight(_normalize_text("米饭150g 热量180kcal"))
        assert "150" in w

    def test_ke_as_unit(self):
        w = _extract_weight(_normalize_text("鸡胸肉 200克 蛋白质40g"))
        assert "200" in w


class TestCategory:
    def test_protein(self):
        assert _classify_food("鸡胸肉") == "protein"

    def test_grain(self):
        assert _classify_food("米饭150g") == "grain"

    def test_mixed(self):
        assert _classify_food("鸡胸肉饭") == "mixed"

    def test_drink(self):
        assert _classify_food("珍珠奶茶") == "drink"

    def test_unknown(self):
        assert _classify_food("未知食物xxx") == "unknown"

    def test_snack(self):
        assert _classify_food("薯片") == "snack"

    def test_vegetable(self):
        assert _classify_food("西兰花") == "vegetable"


class TestFullParse:
    def test_success_with_nutrition(self):
        r = parse_ocr_text("鸡胸肉饭 热量520 蛋白质36 脂肪12 碳水65")
        assert r.success is True
        assert r.total_calories == 520
        assert r.total_protein == 36
        assert r.total_fat == 12
        assert r.total_carbs == 65
        assert len(r.items) == 1

    def test_fail_without_nutrition(self):
        r = parse_ocr_text("鸡胸肉饭")
        assert r.success is False

    def test_category_in_item(self):
        r = parse_ocr_text("鸡胸肉饭 热量520 蛋白质36 脂肪12 碳水65")
        assert r.items[0].category == "mixed"

    def test_weight_in_item(self):
        r = parse_ocr_text("米饭150g 热量180 蛋白质4 脂肪1 碳水40")
        w = r.items[0].weight
        assert "150" in w

    def test_weight_default(self):
        r = parse_ocr_text("鸡胸肉饭 热量520 蛋白质36 脂肪12 碳水65")
        assert r.items[0].weight == "1份"
