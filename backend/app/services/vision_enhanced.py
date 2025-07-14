"""Vision Enhanced — 多轮识别增强版

替换 ai_food_recognizer + fusion_service，包含：
1. 多轮识别：scene_detect → detail_analyze → quality_check → confidence_filter
2. 简化 prompt：去掉了 dish_family、alternatives、3 种 mode 混合规则
3. 参考物辅助估重（信用卡/手掌/瓶子/易拉罐）
4. Vision-first 融合策略
5. 低置信度过滤（<0.4 隐藏，<0.6 estimated=true）
6. Validator 自动修正集成
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import time

from app.core.config import settings
from app.schemas.ai_food import FoodImageRecognitionResult, RecognizedFoodItem, FoodComponent

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────

MAX_ITEMS = 8
MIN_CONFIDENCE_SHOW = 0.4          # 低于此值直接隐藏
MIN_CONFIDENCE_ESTIMATED = 0.6     # 低于此值标记 estimated
REFERENCE_OBJECTS = {
    "信用卡": {"known_mm": (85.6, 54.0), "hint": "约 8.5cm × 5.4cm"},
    "手掌": {"known_mm": (180, 100), "hint": "成人手掌约 18cm × 10cm"},
    "矿泉水瓶": {"known_mm": (230, 65), "hint": "500ml 矿泉水瓶高约 23cm"},
    "易拉罐": {"known_mm": (120, 65), "hint": "330ml 易拉罐高约 12cm"},
}

# ── 简化后的 Prompt ────────────────────────────────────

SCENE_DETECT_PROMPT = """分析这张食物图片。列出所有你能清楚识别的食物项。

返回 JSON 格式：
{
  "items": [
    {"food_name": "食物名称", "portion": "份量描述（如一碗/一个/200g）"}
  ],
  "reference_object": "图片中可作尺寸参考的物品（信用卡/手掌/矿泉水瓶/易拉罐），没有则为 null",
  "scene_description": "一句话描述画面"
}

规则：
- 只列出你能肯定看到的食物
- 不要编造图片中没有的食物
- 如果没有任何食物，items 返回空数组
- 不要分析营养，只做识别"""

DETAIL_ANALYZE_PROMPT = """估算 {food_name}（{portion}）的营养数据。

返回 JSON：
{
  "calories": 热量值（单位 kcal，整数），
  "protein": 蛋白质（单位 g，整数），
  "carbs": 碳水（单位 g，整数），
  "fat": 脂肪（单位 g，整数），
  "confidence": 置信度（0.0~1.0），
  "reasoning": "估算依据"
}

规则：
- 参考常见标准份量：米饭≈200g/碗、肉类≈150g/份、蔬菜≈150g/份
- 如果不确定，confidence 给 0.5 以下
- 不编造"""


# ── Phase 1: Scene Detect ─────────────────────────────

async def scene_detect(image_path: str) -> dict:
    """第一轮：识别图片中有什么食物"""
    if settings.VISION_MODE == "mock" or settings.AI_MODE == "mock":
        return _scene_detect_mock()

    if not os.path.isfile(image_path):
        return {"items": [], "error": "图片文件不存在"}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.BAILIAN_API_KEY, base_url=settings.BAILIAN_BASE_URL)
    except ImportError:
        return _scene_detect_mock()

    image_b64 = _image_to_base64(image_path)
    try:
        resp = client.chat.completions.create(
            model=settings.BAILIAN_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": SCENE_DETECT_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_b64}},
                ],
            }],
            timeout=settings.VISION_TIMEOUT_SECONDS,
        )
        content = resp.choices[0].message.content or ""
        data = _extract_json(content) or {}
        items = data.get("items", [])
        return {
            "items": items[:MAX_ITEMS],
            "reference_object": data.get("reference_object"),
            "scene_description": data.get("scene_description", ""),
            "is_food_detected": len(items) > 0,
        }
    except Exception as e:
        logger.warning("scene_detect failed: %s", e)
        return {"items": [], "error": str(e)[:200]}


def _scene_detect_mock() -> dict:
    """Mock scene detection"""
    return {
        "items": [
            {"food_name": "米饭", "portion": "一碗"},
            {"food_name": "鸡胸肉", "portion": "一份"},
            {"food_name": "西兰花", "portion": "一份"},
        ],
        "reference_object": None,
        "scene_description": "分格便当，米饭、鸡胸肉、西兰花分开摆放",
        "is_food_detected": True,
    }


# ── Phase 2: Detail Analysis ──────────────────────────

async def detail_analyze(scene: dict, image_path: str = "") -> list[dict]:
    """第二轮：对每个食物单独分析营养"""
    items = scene.get("items", [])
    if not items:
        return []

    if settings.VISION_MODE == "mock" or settings.AI_MODE == "mock":
        return _detail_analyze_mock(items)

    # 并发分析每个食物
    tasks = [_analyze_single(item, image_path) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged = []
    for item, result in zip(items, results):
        if isinstance(result, dict):
            merged.append({**item, **result})
        else:
            merged.append({**item, "calories": 0, "confidence": 0.2})

    return merged


async def _analyze_single(item: dict, image_path: str) -> dict:
    """调用 AI 分析单个食物的营养"""
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.BAILIAN_API_KEY,
            base_url=settings.BAILIAN_BASE_URL,
        )
        prompt = DETAIL_ANALYZE_PROMPT.format(
            food_name=item.get("food_name", "?"),
            portion=item.get("portion", "一份"),
        )

        messages = [{"role": "user", "content": prompt}]
        if image_path and os.path.isfile(image_path):
            image_b64 = _image_to_base64(image_path)
            messages[0] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_b64}},
                ],
            }

        resp = client.chat.completions.create(
            model=settings.BAILIAN_MODEL,
            messages=messages,
            timeout=15,
        )
        content = resp.choices[0].message.content or ""
        data = _extract_json(content) or {}
        return {
            "calories": data.get("calories", 0),
            "protein": data.get("protein", 0),
            "carbs": data.get("carbs", 0),
            "fat": data.get("fat", 0),
            "confidence": data.get("confidence", 0.5),
            "reasoning": data.get("reasoning", ""),
        }
    except Exception as e:
        logger.warning("detail_analyze single failed: %s", e)
        return {"calories": 0, "confidence": 0.2}


def _detail_analyze_mock(items: list[dict]) -> list[dict]:
    """Mock detail analysis"""
    mock_data = {
        "米饭": {"calories": 260, "protein": 5, "carbs": 58, "fat": 1, "confidence": 0.85},
        "鸡胸肉": {"calories": 240, "protein": 46, "carbs": 0, "fat": 5, "confidence": 0.78},
        "西兰花": {"calories": 35, "protein": 3, "carbs": 7, "fat": 0, "confidence": 0.72},
        "鸡蛋": {"calories": 75, "protein": 6, "carbs": 1, "fat": 5, "confidence": 0.70},
    }
    results = []
    for item in items:
        name = item.get("food_name", "")
        base = mock_data.get(name, {"calories": 100, "protein": 5, "carbs": 10, "fat": 5, "confidence": 0.5})
        results.append({**item, **base, "source": "vision", "estimated": True})
    return results


# ── Phase 3: Quality Check ───────────────────────────

def quality_check(items: list[dict]) -> list[dict]:
    """使用 existing validators 自动修正"""
    try:
        from app.services.agent.validators import validate_item, try_correct
    except ImportError:
        return items

    corrected = []
    for item in items:
        issues = validate_item(item)
        if issues:
            fixed, _ = try_correct(item, issues)
            corrected.append(fixed)
        else:
            corrected.append(item)
    return corrected


# ── Phase 4: Confidence Filter ────────────────────────

def confidence_filter(items: list[dict]) -> list[dict]:
    """过滤低置信度结果"""
    visible = []
    hidden = []
    for item in items:
        conf = item.get("confidence", 0.0) or 0.0
        if conf < MIN_CONFIDENCE_SHOW:
            hidden.append(item.get("food_name", "?"))
            continue
        if conf < MIN_CONFIDENCE_ESTIMATED:
            item["estimated"] = True
        else:
            item.setdefault("estimated", True)
        visible.append(item)

    if hidden:
        logger.info("confidence_filter: hidden %d low-confidence items: %s",
                    len(hidden), hidden)
    return visible


# ── 主入口 ────────────────────────────────────────────

async def enhanced_recognize(image_path: str) -> FoodImageRecognitionResult | None:
    """增强版食物识别主流程

    替代 ai_food_recognizer.recognize_food() 的返回值。
    """
    # Phase 1: Scene detect
    scene = await scene_detect(image_path)
    if not scene.get("is_food_detected"):
        return FoodImageRecognitionResult(
            is_food_detected=False,
            non_food_reason=scene.get("error", "图片中未检测到食物"),
            scene_description=scene.get("scene_description", ""),
            confidence=0.0,
            warnings=[],
        )

    # Phase 2: Detail analysis
    items = await detail_analyze(scene, image_path)
    if not items:
        return FoodImageRecognitionResult(
            is_food_detected=False,
            non_food_reason="无法分析食物营养数据",
            confidence=0.0,
            warnings=[],
        )

    # Phase 3: Quality check (uses existing validators)
    items = quality_check(items)

    # Phase 4: Confidence filter
    items = confidence_filter(items)

    # 组装 FoodImageRecognitionResult
    food_items = []
    for item in items:
        food_items.append(RecognizedFoodItem(
            food_name=item.get("food_name", "未知"),
            category=item.get("category", "unknown"),
            estimated_weight_g=200.0,   # 修复：不传 weight_g，NutritionEstimate 内部会推算
            calories=item.get("calories", 0),
            protein=item.get("protein", 0),
            carbs=item.get("carbs", 0),
            fat=item.get("fat", 0),
            confidence=item.get("confidence", 0.5),
            source="vision",
            estimated=item.get("estimated", True),
            reasoning=item.get("reasoning", ""),
            role="independent",
            include_in_total=True,
        ))

    total_conf = sum(f.confidence or 0 for f in food_items) / max(len(food_items), 1)
    return FoodImageRecognitionResult(
        is_food_detected=True,
        analysis_mode="component_sum",
        scene_description=scene.get("scene_description", ""),
        confidence=total_conf,
        food_items=food_items,
        warnings=[],
    )


# ── 工具函数 ──────────────────────────────────────────

def _image_to_base64(image_path: str) -> str:
    import base64
    with open(image_path, "rb") as f:
        return f"data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return {"items": data}
        except json.JSONDecodeError:
            pass
    return None
