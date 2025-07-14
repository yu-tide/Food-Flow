"""开放式 AI Vision 食物识别器 — mock / bailian"""
import base64
import json
import logging
import os
import re
import time

from app.core.config import settings
from app.schemas.ai_food import FoodComponent, FoodImageRecognitionResult, RecognizedFoodItem

logger = logging.getLogger(__name__)

RECOGNITION_PROMPT = """你是 FoodFlow 的食物图片识别模型。

先判断图片中食物的结构类型（analysis_mode），再给出识别结果。

如果不是食物：
- is_food_detected = false
- 不编造食物

===================================================
第一步：判断 analysis_mode（这是最重要的判断）
===================================================

component_sum：图片里多个食物边界清晰，能独立识别
- 关键词：米饭+鸡胸肉+西兰花、减脂餐、分格便当、健身餐、水果拼盘、面包+鸡蛋+牛奶
- 判断标准：你能清楚地分别说出每个食物是什么，而不是"这是一道什么菜"
- 每个独立食物作为单独 food_item，role=independent
- 不要生成"便当/减脂餐/健身餐/套餐"作为主项

dish_with_components：图片是一道整体混合菜，食材混在一起
- 关键词：麻辣烫、冒菜、炒饭、炒面、麻辣香锅、火锅、盖饭、混合沙拉
- 判断标准：你无法轻易把每个食材分离出来，只能描述"这碗/这盘里有什么"
- 返回一个 main_dish + 4-8 个 components
- components 的 weight/calories 加总应等于 main_dish
- 必须输出 dish_family 和 alternatives

dish_family 规则 — 根据菜品特征归类到以下家族之一：

川式红汤混合菜：冒菜 / 麻辣烫 / 火锅 / 串串香
  - 特征：红油汤底，多种食材混煮，汤多
干锅炒制类：麻辣香锅 / 干锅菜 / 香辣炒菜
  - 特征：少汤或无汤，干炒/干锅，香辣
米饭盖浇类：盖饭 / 烩饭 / 拌饭 / 咖喱饭 / 卤肉饭
  - 特征：米饭打底 + 浇头/配菜盖在上面
炒饭炒面类：炒饭 / 蛋炒饭 / 炒面 / 炒粉 / 炒河粉
  - 特征：主食与配菜一同翻炒，混合均匀
汤面粉类：牛肉面 / 拉面 / 米线 / 酸辣粉 / 螺蛳粉 / 热干面
  - 特征：面条/粉为主，带汤或拌酱
便当健身餐类：减脂餐 / 健身餐 / 分格便当 / 米饭+肉+蔬菜
  - 特征：多格分装或分区摆放，健康搭配
  注意：此类通常更适合 component_sum，只有食材完全混在一起才用 dish_with_components
沙拉轻食类：沙拉 / 轻食碗 / 水果拼盘 / 波奇饭
  - 特征：冷食为主，蔬菜/水果/蛋白质混合

alternatives 规则：
- primary_dish 的 confidence >= 0.8：alternatives 可为空数组
- confidence 0.6-0.8：必须提供 2-3 个同族 alternatives
- confidence < 0.6：必须提供 3-5 个同族 alternatives
- alternatives 的 confidence 应低于 primary_dish
- 同族内 alternatives confidence 差距 < 0.15 才值得展示

mixed：一道混合主菜 + 明显独立摆放的饮品/汤/小食
- 例如：麻辣烫 + 可乐、盖饭 + 奶茶、沙拉 + 果汁
- main_dish 带 components，independent items 单独列出

CRITICAL 判断优先级：
1. 如果图片里能清楚区分米饭、肉、蔬菜 → 优先 component_sum
2. 如果食材混在一起分不开 → dish_with_components
3. "便当/餐盒/盘子"只是容器，不改变判断：里面食物分得开就用 component_sum

===================================================
第二步：按 analysis_mode 输出 JSON
===================================================

dish_with_components 的 schema：
{
  "is_food_detected": true,
  "analysis_mode": "dish_with_components",
  "scene_description": "...",
  "confidence": 0.82,
  "food_items": [{
    "food_name": "冒菜",
    "role": "main_dish",
    "dish_family": "川式红汤混合菜",
    "alternatives": [
      {"name": "麻辣烫", "confidence": 0.68},
      {"name": "火锅", "confidence": 0.45}
    ],
    "category": "组合菜",
    "estimated_weight_g": 750,
    "calories": 850,
    "protein": 52, "carbs": 65, "fat": 48,
    "confidence": 0.72,
    "reasoning": "红油汤底，多种食材混合，汤量中等，更接近冒菜而非麻辣烫（缺少明显麻味辣椒碎）",
    "components": [
      {"name": "肉类", "estimated_weight_g": 180, "calories": 250, "protein": 28, "fat": 14, "confidence": 0.55, "include_in_total": true},
      {"name": "蔬菜", "estimated_weight_g": 150, "calories": 50, "protein": 3, "carbs": 8, "confidence": 0.6, "include_in_total": true}
    ]
  }],
  "warnings": []
}
重要：components 必须 include_in_total=true，它们的 weight/calories 加总必须等于 main_dish。

component_sum 的 schema：
{
  "is_food_detected": true,
  "analysis_mode": "component_sum",
  "scene_description": "...",
  "confidence": 0.85,
  "food_items": [
    {"food_name": "米饭", "role": "independent", "estimated_weight_g": 200, "calories": 260, "confidence": 0.8, "include_in_total": true},
    {"food_name": "鸡胸肉", "role": "independent", "estimated_weight_g": 150, "calories": 240, "confidence": 0.75, "include_in_total": true},
    {"food_name": "西兰花", "role": "independent", "estimated_weight_g": 100, "calories": 35, "confidence": 0.7, "include_in_total": true}
  ],
  "warnings": []
}
重要：每个 item 都是 role=independent，include_in_total=true。不生成无用的主项。

mixed 的 schema：
{
  "is_food_detected": true,
  "analysis_mode": "mixed",
  "food_items": [
    {"food_name": "麻辣烫", "role": "main_dish", "components": [...], "include_in_total": true},
    {"food_name": "可乐", "role": "independent", "estimated_weight_g": 330, "calories": 140, "include_in_total": true}
  ]
}"""


def _image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return f"data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def _extract_json(text: str) -> dict | None:
    """Extract JSON object from text that may contain markdown fences or extra content."""
    if not text:
        return None
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON inside markdown fences
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _parse_response(content: str) -> FoodImageRecognitionResult | None:
    data = _extract_json(content)
    if not data:
        return None
    try:
        items = [
            RecognizedFoodItem(
                food_name=item.get("food_name", "未知食物"),
                display_name=item.get("display_name"),
                category=item.get("category"),
                estimated_weight_g=item.get("estimated_weight_g"),
                quantity_description=item.get("quantity_description"),
                calories=item.get("calories"),
                protein=item.get("protein"),
                carbs=item.get("carbs"),
                fat=item.get("fat"),
                confidence=item.get("confidence", 0.5),
                source="vision",
                estimated=item.get("estimated", True),
                reasoning=item.get("reasoning"),
                role=item.get("role", "independent"),
                include_in_total=item.get("include_in_total", True),
                dish_family=item.get("dish_family"),
                alternatives=item.get("alternatives", []),
                user_correction=item.get("user_correction"),
                components=[
                    FoodComponent(
                        name=c.get("name", ""),
                        confidence=c.get("confidence", 0.5),
                        estimated_weight_g=c.get("estimated_weight_g"),
                        calories=c.get("calories"),
                        protein=c.get("protein"),
                        carbs=c.get("carbs"),
                        fat=c.get("fat"),
                        role=c.get("role", "ingredient"),
                        include_in_total=c.get("include_in_total", False),
                    )
                    for c in item.get("components", [])
                ],
            )
            for item in data.get("food_items", [])
        ]
        return FoodImageRecognitionResult(
            is_food_detected=data.get("is_food_detected", len(items) > 0),
            analysis_mode=data.get("analysis_mode", "whole_dish"),
            non_food_reason=data.get("non_food_reason"),
            scene_description=data.get("scene_description"),
            confidence=data.get("confidence", 0.5),
            food_items=items,
            warnings=data.get("warnings", []),
        )
    except Exception as e:
        logger.warning("ai_food_recognizer: parse items failed: %s", e)
        return None


def _run_mock(image_path: str) -> FoodImageRecognitionResult:
    """返回逼真的 mock 识别结果，用于测试完整链路"""
    filename = os.path.basename(image_path).lower()

    # 非食物检测
    if any(kw in filename for kw in ["flower", "flower", "花", "plant", "cat", "dog", "car"]):
        return FoodImageRecognitionResult(
            is_food_detected=False,
            non_food_reason="图片中主要是花卉/非食物内容，没有可分析的食物或饮品",
            scene_description="花卉照片",
            confidence=0.93,
            warnings=["未识别到可分析的食物"],
        )

    # 根据文件名关键词切换 mock 模式，方便测试
    if any(kw in filename for kw in ["bento", "mealprep", "fitness", "jianzhi", "减脂", "健身", "分格"]):
        return FoodImageRecognitionResult(
            is_food_detected=True,
            analysis_mode="component_sum",
            scene_description="分格便当，米饭、鸡胸肉、西兰花、鸡蛋分区摆放",
            confidence=0.88,
            food_items=[
                RecognizedFoodItem(food_name="米饭", role="independent", estimated_weight_g=200, calories=260, protein=5, carbs=58, fat=1, confidence=0.85, source="vision"),
                RecognizedFoodItem(food_name="鸡胸肉", role="independent", estimated_weight_g=150, calories=240, protein=46, carbs=0, fat=5, confidence=0.78, source="vision"),
                RecognizedFoodItem(food_name="西兰花", role="independent", estimated_weight_g=100, calories=35, protein=3, carbs=7, fat=0, confidence=0.72, source="vision"),
                RecognizedFoodItem(food_name="鸡蛋", role="independent", estimated_weight_g=50, calories=75, protein=6, carbs=1, fat=5, confidence=0.7, source="vision"),
            ],
            warnings=[],
        )

    # 默认返回 dish_with_components（模拟麻辣烫）
    return FoodImageRecognitionResult(
        is_food_detected=True,
        analysis_mode="dish_with_components",
        scene_description="一碗麻辣烫，包含多种食材和辣油汤底",
        confidence=0.82,
        food_items=[
            RecognizedFoodItem(
                food_name="麻辣烫",
                display_name="麻辣烫",
                dish_family="川式红汤混合菜",
                alternatives=[
                    {"name": "冒菜", "confidence": 0.65},
                    {"name": "火锅", "confidence": 0.4},
                ],
                category="组合菜",
                role="main_dish",
                estimated_weight_g=750.0,
                quantity_description="约一大碗",
                calories=850.0,
                protein=52.0,
                carbs=65.0,
                fat=48.0,
                confidence=0.72,
                source="vision",
                estimated=True,
                reasoning="红油汤底，多种食材混合煮制",
                components=[
                    FoodComponent(name="肉类", estimated_weight_g=180, calories=250, protein=28, fat=14, confidence=0.55, include_in_total=True),
                    FoodComponent(name="丸子/加工肉", estimated_weight_g=100, calories=180, protein=12, carbs=8, fat=12, confidence=0.48, include_in_total=True),
                    FoodComponent(name="豆制品", estimated_weight_g=80, calories=100, protein=10, carbs=4, fat=5, confidence=0.45, include_in_total=True),
                    FoodComponent(name="蔬菜", estimated_weight_g=150, calories=50, protein=3, carbs=8, confidence=0.6, include_in_total=True),
                    FoodComponent(name="粉/面", estimated_weight_g=120, calories=180, protein=3, carbs=40, fat=1, confidence=0.42, include_in_total=True),
                    FoodComponent(name="汤底/油脂", estimated_weight_g=40, calories=90, fat=9, confidence=0.4, include_in_total=True),
                ],
            ),
        ],
        warnings=[],
    )


def _run_bailian(image_path: str) -> FoodImageRecognitionResult:
    if not settings.BAILIAN_API_KEY:
        logger.warning("ai_food_recognizer: BAILIAN_API_KEY not set, falling back to mock")
        return _run_mock(image_path)

    if not os.path.isfile(image_path):
        logger.warning("ai_food_recognizer: image not found: %s", image_path)
        return FoodImageRecognitionResult(
            is_food_detected=False,
            non_food_reason="图片文件不存在",
            warnings=["图片文件不存在"],
        )

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("ai_food_recognizer: openai not installed, falling back to mock")
        return _run_mock(image_path)

    try:
        image_b64 = _image_to_base64(image_path)
    except Exception as e:
        logger.warning("ai_food_recognizer: base64 encode failed: %s", e)
        return FoodImageRecognitionResult(
            is_food_detected=False,
            non_food_reason=f"图片编码失败: {e}",
            warnings=[f"图片编码失败: {e}"],
        )

    client = OpenAI(api_key=settings.BAILIAN_API_KEY, base_url=settings.BAILIAN_BASE_URL)

    t0 = time.time()
    try:
        response = client.chat.completions.create(
            model=settings.BAILIAN_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": RECOGNITION_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_b64}},
                ],
            }],
            timeout=settings.VISION_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content or ""
        elapsed = time.time() - t0

        result = _parse_response(content)
        if result is not None:
            logger.info(
                "ai_food_recognizer: model=%s latency=%.1fs is_food=%s items=%d",
                settings.BAILIAN_VISION_MODEL, elapsed,
                result.is_food_detected, len(result.food_items),
            )
            return result

        logger.warning("ai_food_recognizer: JSON parse failed, raw=%s", content[:300])
        return FoodImageRecognitionResult(
            is_food_detected=False,
            non_food_reason="AI 返回格式异常，无法解析",
            warnings=["AI 返回格式异常"],
        )

    except Exception as e:
        elapsed = time.time() - t0
        logger.warning("ai_food_recognizer: bailian call failed after %.1fs: %s", elapsed, e)
        # Fallback to mock on API failure
        return _run_mock(image_path)


def recognize_food(image_path: str) -> FoodImageRecognitionResult:
    """识别图片中的食物。

    根据 VISION_MODE 配置选择 mock 或 bailian 模式。
    返回统一的 FoodImageRecognitionResult。
    """
    if settings.VISION_MODE == "bailian":
        return _run_bailian(image_path)
    return _run_mock(image_path)
