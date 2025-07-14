"""视觉食物识别服务 — mock / bailian"""
import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VisionFoodItem:
    food_name: str = ""
    estimated_weight: str = ""
    weight_g: int = 0
    category: str = "unknown"
    confidence: float = 0.0
    source: str = "vision"
    reason: str = ""


@dataclass
class VisionResult:
    items: list[VisionFoodItem] = field(default_factory=list)
    engine: str = "mock"
    success: bool = False
    error_message: str | None = None


MOCK_VISION_ITEMS = [
    VisionFoodItem(
        food_name="米饭",
        estimated_weight="约150g",
        weight_g=150,
        category="grain",
        confidence=0.85,
        reason="图中主体为一碗白米饭",
    ),
    VisionFoodItem(
        food_name="鸡胸肉",
        estimated_weight="约120g",
        weight_g=120,
        category="protein",
        confidence=0.80,
        reason="米饭旁边的肉类，呈白色纹理",
    ),
    VisionFoodItem(
        food_name="西兰花",
        estimated_weight="约80g",
        weight_g=80,
        category="vegetable",
        confidence=0.70,
        reason="绿色蔬菜装饰",
    ),
]


def _image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
    return f"data:image/{mime};base64,{data}"


def _run_mock(image_path: str) -> VisionResult:
    return VisionResult(items=MOCK_VISION_ITEMS, engine="vision-mock", success=True)


def _parse_vision_response(raw: str) -> list[VisionFoodItem]:
    """从模型输出中提取 JSON 数组并解析"""
    # 尝试提取 JSON 块
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []

    items = []
    for obj in data:
        if not isinstance(obj, dict):
            continue
        items.append(VisionFoodItem(
            food_name=str(obj.get("food_name", "")),
            estimated_weight=str(obj.get("estimated_weight", "")),
            weight_g=int(obj.get("weight_g", 0)),
            category=str(obj.get("category", "unknown")),
            confidence=float(obj.get("confidence", 0.5)),
            reason=str(obj.get("reason", "")),
        ))
    return items


def _run_bailian(image_path: str) -> VisionResult:
    if not settings.BAILIAN_API_KEY:
        return VisionResult(success=False, error_message="BAILIAN_API_KEY missing")

    if not os.path.isfile(image_path):
        return VisionResult(success=False, error_message=f"image not found: {image_path}")

    try:
        from openai import OpenAI
    except ImportError:
        return VisionResult(success=False, error_message="openai not installed")

    try:
        image_b64 = _image_to_base64(image_path)
    except Exception as e:
        return VisionResult(success=False, error_message=f"base64 encode failed: {e}")

    client = OpenAI(api_key=settings.BAILIAN_API_KEY, base_url=settings.BAILIAN_BASE_URL)

    prompt = (
        "请识别图中的食物，返回 JSON 数组。每个元素包含: food_name(食物名称), "
        "estimated_weight(估算份量如约150g), weight_g(克数), "
        "category(类别: grain/protein/vegetable/drink/snack/mixed/unknown), "
        "confidence(置信度0-1), reason(判断依据)。"
        "只输出 JSON 数组，不要其他内容。"
    )

    t0 = time.time()
    try:
        response = client.chat.completions.create(
            model=settings.BAILIAN_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_b64}},
                ],
            }],
            timeout=settings.VISION_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        elapsed = time.time() - t0

        items = _parse_vision_response(content or "")
        logger.info("vision_service: model=%s latency=%.1fs items=%d",
                    settings.BAILIAN_VISION_MODEL, elapsed, len(items))

        return VisionResult(
            items=items,
            engine="vision-bailian-v1",
            success=len(items) > 0,
        )
    except Exception as e:
        elapsed = time.time() - t0
        logger.warning("vision_service: failed after %.1fs: %s", elapsed, e)
        return VisionResult(success=False, error_message=str(e)[:200])


def recognize_food_from_image(image_path: str, ocr_text: str | None = None) -> VisionResult:
    if settings.VISION_MODE == "bailian":
        return _run_bailian(image_path)
    return _run_mock(image_path)
