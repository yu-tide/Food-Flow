"""用户手动输入食物名称校验器"""

import re

# 常见食物特征字 — 含这些字大概率是食物
_FOOD_KEYWORDS = set(
    "饭菜面粥汤包饺饼粉蛋肉鱼虾鸡鸭牛猪羊豆"
    "果菜蔬瓜茶奶饮汁酒咖啡汤锅煲烧烤蒸煮炸炒拌炖"
    "米麦糕糖薯片壳仁核辣麻香甜酸咸鲜"
)

# 明显非食物黑名单
_NON_FOOD_BLACKLIST: set[str] = {
    "手机", "电脑", "桌子", "椅子", "石头", "花", "鞋子", "衣服",
    "书", "笔", "纸巾", "钥匙", "钱包", "眼镜", "杯子", "碗", "盘子",
    "车", "玩具", "化妆品", "洗发水", "狗", "猫",
}


def validate_manual_food_name(name: str) -> dict:
    """校验用户手动输入的食物名称。

    Returns dict with:
        valid: bool
        normalized_name: str
        reason: str | None
        maybe_non_food: bool
    """
    normalized = name.strip() if name else ""

    # 空
    if not normalized:
        return {"valid": False, "normalized_name": "", "reason": "食物名称不能为空", "maybe_non_food": True}

    # 太长
    if len(normalized) > 30:
        return {"valid": False, "normalized_name": normalized[:30], "reason": "食物名称过长，请控制在 30 字以内", "maybe_non_food": False}

    # 纯数字
    if re.match(r"^\d+$", normalized):
        return {"valid": False, "normalized_name": normalized, "reason": "食物名称不能为纯数字", "maybe_non_food": True}

    # 纯符号/无意义
    if re.match(r"^[!@#$%^&*()_+\-=\[\]{}|;:'\",.<>?/`~\\]+$", normalized):
        return {"valid": False, "normalized_name": normalized, "reason": "食物名称无效，请输入具体食物名", "maybe_non_food": True}

    # 太短且无意义
    if len(normalized) <= 1 and not any(kw in normalized for kw in _FOOD_KEYWORDS):
        return {"valid": False, "normalized_name": normalized, "reason": "食物名称太短，请输入更具体的名称", "maybe_non_food": True}

    # 黑名单完全匹配
    if normalized in _NON_FOOD_BLACKLIST:
        return {"valid": False, "normalized_name": normalized, "reason": f"「{normalized}」不是食物，请输入食物名称", "maybe_non_food": True}

    # 检查是否包含食物特征字
    has_food_kw = any(kw in normalized for kw in _FOOD_KEYWORDS)

    return {
        "valid": True,
        "normalized_name": normalized,
        "reason": None,
        "maybe_non_food": not has_food_kw,
    }
