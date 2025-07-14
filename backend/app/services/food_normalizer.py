"""食物名称标准化器 — 把 AI 自然语言食物名变成适合检索的标准形式"""

import re

# 常见缩写 / 口语 → 标准名称
_NAME_ALIASES: dict[str, str] = {
    "蛋炒饭": "炒饭",
    "家常炒饭": "炒饭",
    "扬州炒饭": "炒饭",
    "白饭": "米饭",
    "白米饭": "米饭",
    "大米饭": "米饭",
    "炒面": "面条",
    "拉面": "面条",
    "汤面": "面条",
    "拌面": "面条",
    "鸡胸": "鸡胸肉",
    "鸡腿": "鸡肉",
    "鸡翅": "鸡肉",
    "猪排": "猪肉",
    "红烧肉": "猪肉",
    "牛排": "牛肉",
    "牛腩": "牛肉",
    "水煮鱼": "鱼",
    "清蒸鱼": "鱼",
    "炒青菜": "青菜",
    "时蔬": "混合蔬菜",
    "凉拌黄瓜": "黄瓜",
    "番茄炒蛋": "番茄炒蛋",
    "蛋花汤": "汤",
    "紫菜汤": "汤",
    "珍珠奶茶": "奶茶",
    "奶盖茶": "奶茶",
    "拿铁": "咖啡",
    "美式": "咖啡",
    "橙汁": "果汁",
    "苹果汁": "果汁",
    "盒饭": "盒饭",
    "便当": "盒饭",
    "快餐": "盒饭",
    "盖浇饭": "盖饭",
    "盖码饭": "盖饭",
    "麻辣香锅": "麻辣香锅",
    "麻辣烫": "麻辣香锅",
    "火锅": "火锅",
    "沙拉": "沙拉",
    "蔬菜沙拉": "沙拉",
    "水果沙拉": "沙拉",
}

# 类别关键词
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "主食": ["饭", "面", "粥", "馒头", "面包", "饼", "粉", "米", "包", "饺", "馄饨"],
    "蛋白质": ["肉", "鸡", "鸭", "鱼", "虾", "蟹", "蛋", "豆腐", "牛", "猪", "羊", "豆"],
    "蔬菜": ["菜", "蔬", "西兰花", "番茄", "黄瓜", "青菜", "白菜", "萝卜", "茄子", "豆角", "辣椒"],
    "饮品": ["茶", "奶", "咖啡", "果汁", "豆浆", "饮", "水", "酒", "可乐", "汽水"],
    "混合菜": ["炒", "烧", "炖", "煮", "蒸", "烤", "炸", "拌", "火锅", "麻辣", "香锅", "盒饭", "便当", "套餐"],
    "零食": ["薯片", "蛋糕", "糖", "巧克力", "饼干", "冰淇淋", "甜点", "坚果", "瓜子"],
}


def _classify(food_name: str) -> str:
    """根据名称关键词判断类别"""
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in food_name:
                return cat
    return "混合菜"


def _decompose(food_name: str) -> list[str]:
    """尝试把复合食物名拆成可能的组成成分"""
    components: list[str] = []
    # 米饭类
    if any(kw in food_name for kw in ["饭", "炒饭", "盖饭", "盒饭"]):
        components.append("米饭")
    # 面类
    if any(kw in food_name for kw in ["面", "粉", "米线"]):
        components.append("面条")
    # 肉类
    for meat, label in [("鸡", "鸡肉"), ("鸭", "鸭肉"), ("猪", "猪肉"), ("牛", "牛肉"), ("鱼", "鱼"), ("虾", "虾")]:
        if meat in food_name:
            components.append(label)
    # 蛋
    if "蛋" in food_name:
        components.append("鸡蛋")
    # 蔬菜
    if any(kw in food_name for kw in ["菜", "蔬"]):
        components.append("蔬菜")
    # 油
    if any(kw in food_name for kw in ["炒", "烧", "炸", "煎", "炖"]):
        if "食用油" not in components:
            components.append("食用油")
    return components if components else [food_name]


def _build_search_queries(food_name: str, category: str) -> list[str]:
    """构建用于检索的查询关键词"""
    name = food_name.strip()
    queries = [name]
    parts = re.split(r"[炒烧炖煮蒸烤炸拌]", name)
    if len(parts) > 1:
        for p in parts:
            p = p.strip()
            if len(p) >= 2:
                queries.append(p)
    queries.append(f"{name} 每100g 营养")
    queries.append(f"{category} 热量")
    seen = set()
    unique = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            unique.append(q)
    return unique[:6]


def normalize_food_name(
    food_name: str,
    category: str | None = None,
    scene_description: str | None = None,
) -> dict:
    """标准化食物名称，返回便于检索的结构。

    Returns dict with:
        normalized_name, search_queries, category, possible_components
    """
    name = food_name.strip()

    # Alias lookup
    normalized = _NAME_ALIASES.get(name, name)

    # Category detection
    if not category or category == "unknown":
        category = _classify(normalized)

    # Decompose
    components = _decompose(normalized)

    # Search queries
    queries = _build_search_queries(normalized, category)

    return {
        "normalized_name": normalized,
        "search_queries": queries,
        "category": category,
        "possible_components": components,
    }
