"""图像食物存在性校验 — 判断用户新增食物是否出现在图片中"""
import base64
import json
import logging
import os
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

JSON_SCHEMA = '''{{"present": "true|false|uncertain", "reason": "简短判断依据"}}'''


def _build_presence_prompt(context: str, food_name: str) -> str:
    return f"""请判断图片中是否存在用户新增的食物。

已识别的主菜：{context}
用户新增食物：{food_name}

规则：
1. 只判断图片中是否可见该食物
2. 如果食物明显不存在，返回 present=false
3. 如果是组合菜中可能出现的配料（被遮挡/不明显），返回 present=uncertain
4. 只有在图片中能明确看到的才返回 present=true
5. 不要把"用户输入"当事实

返回严格 JSON：
{JSON_SCHEMA}"""


def _check_mock(
    image_path: str, food_name: str, context_food_items: list[str],
) -> dict:
    """Mock 模式：基于食物名和上下文做合理判断"""
    context_str = " ".join(context_food_items).lower() if context_food_items else ""
    name = food_name.strip().lower()

    # Foods that commonly appear in composite dishes — might be present even if not visible
    composite_ingredients = {
        "青豆", "胡萝卜", "玉米", "葱花", "葱", "蒜", "姜",
        "酱油", "油", "食用油", "盐", "糖", "芝麻", "辣椒", "花椒",
        "豆皮", "豆腐皮", "粉条", "粉丝", "金针菇", "蘑菇", "木耳",
        "青菜", "白菜", "生菜", "菠菜", "豆芽",
        "鸡蛋", "鹌鹑蛋",
    }

    # Obvious mismatches
    staple_only = {"米饭", "馒头", "面条", "面包", "饼", "粥"}
    is_staple = name in staple_only
    context_is_staple = any(kw in context_str for kw in staple_only)

    # If context is 麻辣烫/火锅 and user adds rice — not present
    has_composite = any(kw in context_str for kw in ("麻辣烫", "麻辣香锅", "冒菜", "火锅", "涮锅"))
    if has_composite and is_staple and not context_is_staple:
        return {"present": "false", "reason": f"图片中未看到{name}，画面主要为{context_food_items[0] if context_food_items else '菜品'}"}

    # If the food appears to be a reasonable ingredient
    if name in composite_ingredients:
        if has_composite:
            return {"present": "uncertain", "reason": f"可能作为配料存在，但图片中不够清晰"}

    # If not obviously wrong, allow but mark uncertain
    return {"present": "uncertain", "reason": "图片中不够清晰，由用户手动补充"}


def _check_bailian(
    image_path: str, food_name: str, context_food_items: list[str],
) -> dict:
    if not settings.BAILIAN_API_KEY:
        return _check_mock(image_path, food_name, context_food_items)

    if not os.path.isfile(image_path):
        return {"present": "uncertain", "reason": "图片文件不可用，跳过校验"}

    try:
        from openai import OpenAI
    except ImportError:
        return _check_mock(image_path, food_name, context_food_items)

    try:
        with open(image_path, "rb") as f:
            image_b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return _check_mock(image_path, food_name, context_food_items)

    context = ", ".join(context_food_items) if context_food_items else "未知"
    prompt = _build_presence_prompt(context, food_name)

    client = OpenAI(api_key=settings.BAILIAN_API_KEY, base_url=settings.BAILIAN_BASE_URL)

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
            timeout=15,
        )
        content = response.choices[0].message.content or ""
        data = _extract_json(content)
        if data:
            return data
        return _check_mock(image_path, food_name, context_food_items)
    except Exception as e:
        logger.warning("presence_checker: AI call failed: %s", e)
        return _check_mock(image_path, food_name, context_food_items)


def _extract_json(text: str) -> dict | None:
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
    return None


def check_food_presence(
    image_path: str,
    food_name: str,
    context_food_items: list[str],
) -> dict:
    """检查用户新增食物是否出现在图片中。

    Returns dict with: present ("true"|"false"|"uncertain"), reason
    """
    if settings.VISION_MODE == "bailian":
        return _check_bailian(image_path, food_name, context_food_items)
    return _check_mock(image_path, food_name, context_food_items)
