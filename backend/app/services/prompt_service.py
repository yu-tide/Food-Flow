"""AI Prompt 构建服务"""

MEAL_LABELS = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "你是一名专业营养师，请根据用户的餐食识别结果生成简洁、可靠的饮食建议。"
        "输出 3 条建议，每条 1-2 句话，用换行分隔。不要 markdown。"
        "必须使用输入中列出的实际食物名称，不要自行改写或虚构食物。"
        "如果标注为'估算结果'，说明'建议基于估算数据，用户可确认后获得更准确分析'。"
        "如果数据有限，说明'基于当前识别数据'。只输出建议内容。"
    ),
}


def build_user_message(
    *,
    food_name: str = "",
    meal_type: str = "",
    total_calories: int = 0,
    protein: int = 0,
    carbs: int = 0,
    fat: int = 0,
    ocr_text: str = "",
    remark: str = "",
    estimated: bool = False,
) -> dict:
    meal_label = MEAL_LABELS.get(meal_type, meal_type or "未知")
    parts = [
        "请根据以下餐食数据生成 3 条中文建议。",
        f"食物名称：{food_name or '未识别'}",
        f"餐别：{meal_label}",
        f"热量：{total_calories} kcal",
        f"蛋白质：{protein}g",
        f"碳水：{carbs}g",
        f"脂肪：{fat}g",
    ]
    if estimated:
        parts.append("注意：以上数据为系统估算结果，并非精确测量值。")
    if ocr_text:
        parts.append(f"OCR 识别文本：{ocr_text}")
    if remark:
        parts.append(f"用户备注：{remark}")
    content = "\n".join(parts)
    return {"role": "user", "content": content}


FALLBACK_SUMMARY = "\n".join([
    "这餐营养搭配基本合理，建议继续保持。",
    "可适当增加蔬菜摄入，提高膳食纤维比例。",
    "注意控制总热量，避免高油高盐烹饪方式。",
])
