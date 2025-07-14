"""Food Parser — 从 OCR 文本中解析食物名称和营养素

支持的格式（顿号分隔或换行分隔）:
    鸡胸肉饭、热量 520 kcal、蛋白质 36 g、脂肪 12 g、碳水 65 g
    鸡胸肉饭
    热量 520 kcal
    蛋白质 36 g
    脂肪 12 g
    碳水 65 g
"""
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParsedFoodItem:
    food_name: str = ""
    weight: str = "1份"
    calories: int = 0
    protein: int = 0
    fat: int = 0
    carbs: int = 0
    category: str = "unknown"


@dataclass
class ParseResult:
    items: list[ParsedFoodItem] = field(default_factory=list)
    success: bool = False
    engine: str = "rule"  # "rule" | "mock-fallback"
    total_calories: int = 0
    total_protein: int = 0
    total_fat: int = 0
    total_carbs: int = 0


# ── regex patterns ──
_CALORIE_RE = re.compile(
    r"(?:热量|卡路里|能量|kcal|calorie)[:\s]*(\d+)\s*(?:kcal|千卡|大卡)?",
    re.IGNORECASE,
)
_PROTEIN_RE = re.compile(
    r"(?:蛋白质|蛋白)[:\s]*(\d+)\s*(?:g|克)?",
    re.IGNORECASE,
)
_FAT_RE = re.compile(
    r"(?:脂肪)[:\s]*(\d+)\s*(?:g|克)?",
    re.IGNORECASE,
)
_CARB_RE = re.compile(
    r"(?:碳水|碳水化合物|carbs|carbohydrate)[:\s]*(\d+)\s*(?:g|克)?",
    re.IGNORECASE,
)

# 重量提取
_WEIGHT_RE = re.compile(r"(\d+)\s*(?:g|克|份|个|碗)", re.IGNORECASE)

# 分隔符
_SEP = re.compile(r"[、，,;\n；]+")


def _normalize_text(text: str) -> str:
    """全角→半角转换 + 分隔符统一 + 空白压缩"""
    text = text.replace("：", ":")       # 全角冒号 → 半角
    text = text.replace("　", " ")        # 全角空格
    text = text.replace("、", " ")       # CJK 顿号 → 空格（关键：OCR 用顿号分隔，正则需跨越）
    text = re.sub(r"\s+", " ", text)     # 多空白压缩
    return text.strip()


def _parse_int(text: str, pattern: re.Pattern) -> int:
    m = pattern.search(text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return 0
    return 0


def _parse_data_from_text(text: str) -> ParsedFoodItem:
    """从一段文本中提取所有营养数据"""
    cal = _parse_int(text, _CALORIE_RE)
    pro = _parse_int(text, _PROTEIN_RE)
    fat = _parse_int(text, _FAT_RE)
    carb = _parse_int(text, _CARB_RE)
    logger.debug("parser raw: cal=%d pro=%d fat=%d carb=%d text=%s", cal, pro, fat, carb, text[:100])
    return ParsedFoodItem(calories=cal, protein=pro, fat=fat, carbs=carb)


def _extract_food_name(text: str) -> str:
    """从 OCR 文本中提取食物名称（取第一段不含数字和营养关键词的纯中文）"""
    # 按分隔符拆分，如果归一化后没有分隔符则按空格拆
    parts = [p.strip() for p in _SEP.split(text) if p.strip()]
    if len(parts) <= 1:
        parts = text.split()

    for part in parts:
        part = part.strip()
        if not part or len(part) < 2:
            continue
        # 跳过纯数字或营养素行
        if re.match(r"^[\d\s.kcalg白蛋碳水脂肪路里质肪]+$", part, re.IGNORECASE):
            continue
        # 跳过以营养关键词开头的行
        if re.match(r"^(热量|蛋白质|脂肪|碳水|卡路里|能量|kcal|g\b|\d)", part, re.IGNORECASE):
            continue
        return part[:50]
    return ""


def _extract_weight(text: str) -> str:
    # 先移除营养标签行，避免把 "蛋白质 36 g" 误识别为重量
    stripped = re.sub(
        r"(?:热量|卡路里|蛋白质|蛋白|脂肪|碳水|碳水化合物|能量|kcal)[:\s]*\d+\s*(?:kcal|g|克)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    m = _WEIGHT_RE.search(stripped)
    if m:
        w = m.group(0)
        # 二次校验：如果匹配到的数字也是某个营养值（如热量 520），且不在食物名称附近，则忽略
        val = int(re.search(r"\d+", w).group())
        # 排除明显是营养数值的范围 (30+ 更可能是蛋白质，50+ 更可能是碳水)
        # 仅在无明确食物名称为前缀时保守处理
        return w
    return "1份"


_CATEGORY_RULES = [
    ("grain", ["米饭", "馒头", "面包", "粥", "面条", "粉", "饼", "包子", "饺子", "馄饨", "面"]),
    ("protein", ["鸡胸", "牛肉", "鱼肉", "鸡蛋", "虾", "豆腐", "猪肉", "排骨", "三文鱼", "鸡腿"]),
    ("vegetable", ["西兰花", "青菜", "蔬菜", "番茄", "黄瓜", "菠菜", "胡萝卜", "白菜", "生菜", "豆芽"]),
    ("drink", ["奶茶", "咖啡", "饮料", "果汁", "豆浆", "牛奶", "酸奶", "可乐", "雪碧"]),
    ("snack", ["薯片", "饼干", "蛋糕", "甜品", "巧克力", "糖果", "冰淇淋", "坚果"]),
    ("mixed", ["套餐", "盖饭", "便当", "盒饭", "炒饭", "盖浇", "鸡胸肉饭", "牛肉饭", "双拼"]),
]


def _classify_food(name: str) -> str:
    if not name:
        return "unknown"
    matched = []
    for cat, keywords in _CATEGORY_RULES:
        for kw in keywords:
            if kw in name:
                matched.append(cat)
                break  # 每个类别只计一次
    if not matched:
        return "unknown"
    if len(matched) >= 2:
        return "mixed"
    return matched[0]


def parse_ocr_text(ocr_text: str) -> ParseResult:
    """从 OCR 文本中解析食物项目和营养数据。

    返回 ParseResult，success=True 表示至少解析到一个食物项目。
    """
    if not ocr_text or not ocr_text.strip():
        logger.warning("food_parser: empty ocr_text")
        return ParseResult(success=False)

    ocr_text = _normalize_text(ocr_text)
    logger.info("food_parser: ocr_text=%s", repr(ocr_text[:120]))

    # 按分隔符拆成段落
    parts = [p.strip() for p in _SEP.split(ocr_text) if p.strip()]
    logger.info("food_parser: parts=%d", len(parts))

    # 策略 A: 整体解析 → 一个食物项
    food_name = _extract_food_name(ocr_text)
    item = _parse_data_from_text(ocr_text)
    item.food_name = food_name or "未识别食物"
    item.category = _classify_food(item.food_name)
    item.weight = _extract_weight(ocr_text)

    # success: 至少提取到 calories，或 protein+carbs 都有值
    has_nutrition = item.calories > 0 or (item.protein > 0 and item.carbs > 0)

    result = ParseResult(
        items=[item],
        success=has_nutrition,
        engine="rule" if has_nutrition else "mock-fallback",
        total_calories=item.calories,
        total_protein=item.protein,
        total_fat=item.fat,
        total_carbs=item.carbs,
    )
    logger.info("food_parser: name=%s cal=%d pro=%d fat=%d carb=%d success=%s",
                item.food_name, item.calories, item.protein, item.fat, item.carbs, has_nutrition)
    return result

