"""Nutrition Estimator 测试"""
from app.services.nutrition_estimator import estimate_nutrition


class TestEstimate:
    def test_rice_150g(self):
        r = estimate_nutrition("米饭", weight_g=150)
        assert r.calories == 174  # 116 * 1.5
        assert r.protein == 3    # 2.6 * 1.5 = 3.9 → int 3
        assert r.carbs == 38     # 25.9 * 1.5 = 38.85 → int 38
        assert r.fat == 0        # 0.3 * 1.5 = 0.45 → int 0
        assert r.estimated is True
        assert r.confidence > 0.7

    def test_rice_no_weight(self):
        r = estimate_nutrition("米饭")
        assert r.calories == 116  # per 100g
        assert r.confidence > 0

    def test_chicken_breast_200g(self):
        r = estimate_nutrition("鸡胸肉", weight_g=200)
        assert r.protein == 62  # 31 * 2

    def test_broccoli(self):
        r = estimate_nutrition("西兰花", weight_g=100)
        assert r.calories == 34
        assert r.protein == 2

    def test_serving_chicken_rice(self):
        r = estimate_nutrition("鸡胸肉饭")
        assert r.calories == 520
        assert r.protein == 36
        assert r.carbs == 65
        assert r.fat == 12
        assert r.confidence > 0.5

    def test_burger(self):
        r = estimate_nutrition("汉堡")
        assert r.calories == 295
        assert r.protein == 17

    def test_milk_tea(self):
        r = estimate_nutrition("奶茶")
        assert r.calories == 70

    def test_unknown_food(self):
        r = estimate_nutrition("未知黑暗料理")
        assert r.calories == 0
        assert r.confidence == 0.0
        assert r.estimated is True

    def test_empty_name(self):
        r = estimate_nutrition("")
        assert r.calories == 0
        assert r.confidence == 0.0

    def test_fuzzy_match(self):
        # "白米饭" won't exact match but fuzzy should find "米饭"
        r = estimate_nutrition("白米饭", weight_g=100)
        assert r.calories == 116
        assert r.confidence >= 0.5
