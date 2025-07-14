"""AI Cache hash 测试"""
import pytest
from app.services.ai_service import _build_cache_key, CACHE_PREFIX


class TestCacheKey:
    def test_same_input_same_key(self):
        k1 = _build_cache_key("鸡胸肉饭", 520, 36, 65, 12, "lunch")
        k2 = _build_cache_key("鸡胸肉饭", 520, 36, 65, 12, "lunch")
        assert k1 == k2

    def test_different_food_different_key(self):
        k1 = _build_cache_key("鸡胸肉饭", 520, 36, 65, 12, "lunch")
        k2 = _build_cache_key("牛肉面", 520, 36, 65, 12, "lunch")
        assert k1 != k2

    def test_different_calories_different_key(self):
        k1 = _build_cache_key("鸡胸肉饭", 520, 36, 65, 12, "lunch")
        k2 = _build_cache_key("鸡胸肉饭", 680, 36, 65, 12, "lunch")
        assert k1 != k2

    def test_key_has_prefix(self):
        k = _build_cache_key("鸡胸肉饭", 520, 36, 65, 12, "lunch")
        assert k.startswith(CACHE_PREFIX + ":")

    def test_key_length(self):
        k = _build_cache_key("鸡胸肉饭", 520, 36, 65, 12, "lunch")
        # prefix + ":" + 16 hex chars
        assert len(k) == len(CACHE_PREFIX) + 1 + 16


class TestGenerateSummaryMock:
    """mock 模式不依赖外部 API"""
    def test_mock_returns_summary(self):
        from app.services.ai_service import generate_summary
        from app.core.config import settings

        orig = settings.AI_MODE
        try:
            # 强制 mock 模式避免依赖外部 API
            object.__setattr__(settings, 'AI_MODE', 'mock')
            r = generate_summary(food_name="测试", total_calories=520)
            assert r.success is True
            assert r.engine == "ai-mock-v1"
            assert len(r.text) > 0
        finally:
            object.__setattr__(settings, 'AI_MODE', orig)
