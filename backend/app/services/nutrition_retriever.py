"""营养参考检索器 — 轻量 RAG，内置基础营养参考数据，支持关键词/类别检索"""

from app.schemas.ai_food import NutritionReference

# 每 100g 数据: (calories, protein, carbs, fat)
_P100 = tuple[float, float, float, float]

# ============================================================
# 主食类
# ============================================================
_GRAIN: dict[str, tuple[_P100, list[str], str | None]] = {
    "米饭": ((116, 2.6, 25.9, 0.3), ["白米饭", "大米饭", "白饭", "蒸饭"], "熟重，约 116 kcal/100g"),
    "面条": ((110, 3.5, 22.0, 0.5), ["面", "拉面", "汤面", "拌面", "挂面"], "熟重，约 110 kcal/100g"),
    "炒饭": ((180, 5.0, 26.0, 6.0), ["蛋炒饭", "扬州炒饭", "家常炒饭"], "含油含蛋，约 180 kcal/100g"),
    "粥": ((46, 1.1, 9.7, 0.2), ["白粥", "稀饭", "小米粥", "杂粮粥"], "稀稠度影响热量"),
    "馒头": ((223, 7.0, 44.2, 1.1), ["白馒头", "馒头", "蒸馒头"], "约 223 kcal/100g"),
    "面包": ((313, 9.0, 58.5, 5.0), ["吐司", "白面包", "全麦面包"], "白面包约 313 kcal/100g"),
    "油条": ((386, 6.9, 51.0, 17.6), ["油炸鬼"], "油炸食品，热量高"),
    "饺子": ((220, 8.0, 28.0, 8.0), ["水饺", "蒸饺", "煎饺"], "猪肉馅，约 220 kcal/100g"),
    "馄饨": ((180, 7.0, 25.0, 5.0), ["抄手", "云吞"], "约 180 kcal/100g"),
    "包子": ((220, 8.0, 32.0, 7.0), ["肉包", "菜包", "小笼包"], "肉馅约 220 kcal/100g"),
    "米粉": ((110, 2.0, 24.0, 0.4), ["米线", "河粉"], "约 110 kcal/100g"),
    "饼": ((280, 8.0, 45.0, 8.0), ["大饼", "烧饼", "煎饼", "烙饼"], "含油，约 280 kcal/100g"),
}

# ============================================================
# 蛋白质类
# ============================================================
_PROTEIN: dict[str, tuple[_P100, list[str], str | None]] = {
    "鸡蛋": ((155, 12.6, 1.1, 10.6), ["水煮蛋", "煮鸡蛋", "煎蛋", "炒蛋", "蛋花"], "一个约 50-60g(可食部分)"),
    "鸡胸肉": ((133, 31.0, 0.0, 1.2), ["鸡胸", "鸡脯肉", "白肉"], "去皮，约 133 kcal/100g"),
    "鸡肉": ((167, 25.0, 0.0, 7.0), ["鸡腿", "鸡翅", "烧鸡", "炸鸡"], "带皮/调味后偏高"),
    "牛肉": ((250, 26.0, 0.0, 15.0), ["牛排", "牛腩", "肥牛", "酱牛肉", "红烧牛肉"], "视肥瘦浮动"),
    "猪肉": ((395, 13.2, 0.0, 37.0), ["红烧肉", "猪排", "五花肉", "排骨", "回锅肉"], "肥瘦差异大，五花肉约 395"),
    "瘦猪肉": ((143, 20.3, 0.0, 6.2), ["瘦肉", "瘦猪肉", "猪里脊"], "纯瘦肉约 143 kcal/100g"),
    "羊肉": ((203, 19.0, 0.0, 14.1), ["羊排", "涮羊肉", "羊肉串"], "约 203 kcal/100g"),
    "鱼": ((105, 17.5, 0.0, 3.5), ["鱼肉", "清蒸鱼", "红烧鱼", "烤鱼", "水煮鱼"], "淡水鱼均值"),
    "虾": ((93, 18.6, 0.0, 1.5), ["虾仁", "基围虾", "小龙虾", "虾肉"], "约 93 kcal/100g"),
    "豆腐": ((76, 8.1, 2.8, 3.7), ["老豆腐", "嫩豆腐", "豆干", "豆皮"], "约 76 kcal/100g"),
    "豆干": ((140, 16.2, 4.0, 7.0), ["豆腐干", "香干", "卤豆干"], "约 140 kcal/100g"),
}

# ============================================================
# 蔬菜类
# ============================================================
_VEGETABLE: dict[str, tuple[_P100, list[str], str | None]] = {
    "青菜": ((20, 2.0, 3.0, 0.2), ["炒青菜", "上海青", "小油菜", "小白菜", "油菜"], "清炒约 20-40 kcal/100g(含油)"),
    "西兰花": ((34, 2.8, 7.0, 0.4), ["花椰菜", "绿菜花", "西蓝花"], "约 34 kcal/100g"),
    "番茄": ((18, 0.9, 3.9, 0.2), ["西红柿", "番茄炒蛋"], "约 18 kcal/100g(生)"),
    "黄瓜": ((16, 0.7, 2.9, 0.2), ["凉拌黄瓜", "拍黄瓜", "黄瓜片"], "约 16 kcal/100g"),
    "白菜": ((13, 1.5, 2.2, 0.2), ["大白菜", "娃娃菜", "小白菜"], "约 13 kcal/100g"),
    "胡萝卜": ((41, 0.9, 9.6, 0.2), ["红萝卜", "胡萝卜丝"], "约 41 kcal/100g"),
    "土豆": ((81, 2.0, 17.5, 0.2), ["马铃薯", "土豆丝", "土豆片", "薯条"], "约 81 kcal/100g(煮)"),
    "茄子": ((23, 1.1, 4.0, 0.3), ["烧茄子", "炒茄子", "凉拌茄子"], "清炒约 60-80 kcal/100g(吸油)"),
    "混合蔬菜": ((35, 2.0, 5.0, 0.5), ["时蔬", "蔬菜", "青菜", "素菜", "炒素"], "一般炒蔬菜均值"),
    "沙拉": ((50, 2.0, 5.0, 2.5), ["蔬菜沙拉", "水果沙拉", "沙拉菜"], "含酱汁，约 50 kcal/100g"),
}

# ============================================================
# 饮品类
# ============================================================
_DRINK: dict[str, tuple[_P100, list[str], str | None]] = {
    "牛奶": ((54, 3.0, 4.9, 3.1), ["纯牛奶", "鲜奶", "全脂牛奶", "脱脂牛奶"], "全脂约 54 kcal/100ml"),
    "豆浆": ((31, 2.4, 2.4, 1.5), ["豆奶", "现磨豆浆", "甜豆浆"], "无糖约 31，加糖约 45"),
    "奶茶": ((60, 1.5, 9.0, 2.0), ["珍珠奶茶", "奶盖茶", "奶茶", "果茶"], "含糖含奶，约 60 kcal/100ml"),
    "果汁": ((45, 0.5, 10.5, 0.2), ["橙汁", "苹果汁", "西瓜汁", "鲜榨果汁"], "约 45 kcal/100ml"),
    "咖啡": ((5, 0.2, 0.5, 0.3), ["美式", "黑咖啡", "清咖"], "无糖无奶美式约 5 kcal/100ml"),
    "拿铁咖啡": ((40, 2.0, 3.5, 2.0), ["拿铁", "卡布奇诺", "奶咖"], "含牛奶约 40 kcal/100ml"),
    "无糖茶": ((1, 0.0, 0.0, 0.0), ["清茶", "绿茶", "红茶", "乌龙茶", "普洱茶", "花茶"], "纯茶几乎无热量"),
    "可乐": ((42, 0.0, 10.6, 0.0), ["汽水", "碳酸饮料", "雪碧"], "含糖约 42 kcal/100ml"),
    "水": ((0, 0.0, 0.0, 0.0), ["白水", "饮用水", "矿泉水", "纯净水", "白开水"], "无热量"),
}

# ============================================================
# 混合菜 / 套餐
# ============================================================
_MIXED: dict[str, tuple[_P100, list[str], str | None]] = {
    "盒饭": ((150, 7.0, 20.0, 5.0), ["便当", "快餐", "工作餐", "套餐"], "二荤一素均值"),
    "盖饭": ((160, 9.0, 22.0, 5.5), ["盖浇饭", "盖码饭", "浇汁饭"], "含米饭+浇头"),
    "麻辣香锅": ((180, 12.0, 10.0, 11.0), ["麻辣烫", "冒菜", "串串", "火锅菜"], "含油含辣，约 180 kcal/100g"),
    "火锅": ((150, 10.0, 5.0, 10.0), ["涮锅", "涮火锅", "麻辣火锅"], "视食材浮动"),
    "炒菜": ((120, 8.0, 8.0, 7.0), ["家常菜", "小炒", "热菜", "中式炒菜"], "一般炒菜均值"),
    "汤": ((30, 2.0, 2.0, 1.0), ["菜汤", "蛋花汤", "紫菜汤", "番茄汤", "骨头汤", "鸡汤"], "清汤约 30 kcal/100ml"),
    "烤肉": ((250, 22.0, 0.5, 17.0), ["韩式烤肉", "日式烤肉", "烧烤", "BBQ"], "视肉种类浮动"),
    "炸鸡": ((290, 20.0, 12.0, 18.0), ["炸鸡腿", "炸鸡翅", "炸鸡块", "鸡排", "炸鸡排"], "油炸，热量高"),
}

# ============================================================
# 零食/糕点
# ============================================================
_SNACK: dict[str, tuple[_P100, list[str], str | None]] = {
    "薯片": ((536, 7.0, 53.0, 34.0), ["薯条", "炸薯条", "炸薯片", "土豆片"], "油炸零食，热量很高"),
    "蛋糕": ((350, 4.0, 45.0, 16.0), ["奶油蛋糕", "生日蛋糕", "巧克力蛋糕", "甜点"], "约 350 kcal/100g"),
    "饼干": ((450, 8.0, 65.0, 18.0), ["曲奇", "苏打饼干", "夹心饼干"], "约 450 kcal/100g"),
    "巧克力": ((546, 5.0, 60.0, 31.0), ["巧克力糖", "黑巧克力", "牛奶巧克力"], "约 546 kcal/100g"),
    "冰淇淋": ((200, 3.5, 24.0, 10.0), ["冰激凌", "雪糕", "甜筒", "冰棍"], "约 200 kcal/100g"),
    "坚果": ((600, 20.0, 16.0, 53.0), ["核桃", "杏仁", "腰果", "瓜子", "花生"], "约 600 kcal/100g, 热量高"),
}

# ============================================================
# 类别兜底默认值 (per 100g)
# ============================================================
_CATEGORY_FALLBACK: dict[str, _P100] = {
    "主食": (150, 4.0, 28.0, 2.0),
    "蛋白质": (180, 22.0, 1.0, 10.0),
    "蔬菜": (35, 2.0, 5.0, 0.5),
    "饮品": (50, 1.5, 8.0, 1.5),
    "混合菜": (160, 9.0, 15.0, 8.0),
    "零食": (400, 6.0, 50.0, 20.0),
}

_ALL_ENTRIES: dict[str, tuple[_P100, list[str], str | None]] = {}
_ALL_ENTRIES.update(_GRAIN)
_ALL_ENTRIES.update(_PROTEIN)
_ALL_ENTRIES.update(_VEGETABLE)
_ALL_ENTRIES.update(_DRINK)
_ALL_ENTRIES.update(_MIXED)
_ALL_ENTRIES.update(_SNACK)


def retrieve_nutrition_references(
    food_name: str,
    category: str | None = None,
    search_queries: list[str] | None = None,
    limit: int = 5,
) -> list[NutritionReference]:
    """根据食物名/类别/搜索词检索营养参考数据。

    匹配优先级: 精确别名匹配 > 名称包含匹配 > 类别匹配 > 类别兜底
    """
    queries = list(dict.fromkeys(
        ([food_name] if food_name else []) + (search_queries or [])
    ))  # dedup preserving order
    results: list[NutritionReference] = []
    seen_names: set[str] = set()

    # Level 1: exact alias match
    for query in queries:
        for name, (vals, aliases, note) in _ALL_ENTRIES.items():
            if name in seen_names:
                continue
            if query == name or query in aliases:
                seen_names.add(name)
                results.append(NutritionReference(
                    name=name,
                    category=category,
                    calories_per_100g=vals[0],
                    protein_per_100g=vals[1],
                    carbs_per_100g=vals[2],
                    fat_per_100g=vals[3],
                    source="rag",
                    confidence=0.8,
                    note=note,
                ))

    # Level 2: contains match
    if len(results) < limit:
        for query in queries:
            ql = query.lower()
            for name, (vals, aliases, note) in _ALL_ENTRIES.items():
                if name in seen_names:
                    continue
                if ql in name.lower() or any(ql in a.lower() for a in aliases):
                    seen_names.add(name)
                    results.append(NutritionReference(
                        name=name, category=category,
                        calories_per_100g=vals[0], protein_per_100g=vals[1],
                        carbs_per_100g=vals[2], fat_per_100g=vals[3],
                        source="rag", confidence=0.6, note=note,
                    ))

    # Level 3: category match (return top matches from same category)
    if len(results) < limit and category:
        cat_entries = [
            (n, v, a, nt) for n, (v, a, nt) in _ALL_ENTRIES.items()
            if n not in seen_names and _get_entry_category(n) == category
        ]
        for name, vals, _aliases, note in cat_entries[:limit - len(results)]:
            seen_names.add(name)
            results.append(NutritionReference(
                name=name, category=category,
                calories_per_100g=vals[0], protein_per_100g=vals[1],
                carbs_per_100g=vals[2], fat_per_100g=vals[3],
                source="rag", confidence=0.4, note=note,
            ))

    # Level 4: category fallback
    if not results and category in _CATEGORY_FALLBACK:
        vals = _CATEGORY_FALLBACK[category]
        results.append(NutritionReference(
            name=f"{category}通用参考",
            category=category,
            calories_per_100g=vals[0], protein_per_100g=vals[1],
            carbs_per_100g=vals[2], fat_per_100g=vals[3],
            source="rag", confidence=0.3,
            note=f"{category}类别兜底估算值",
        ))

    return results[:limit]


def _get_entry_category(name: str) -> str:
    if name in _GRAIN:
        return "主食"
    if name in _PROTEIN:
        return "蛋白质"
    if name in _VEGETABLE:
        return "蔬菜"
    if name in _DRINK:
        return "饮品"
    if name in _MIXED:
        return "混合菜"
    if name in _SNACK:
        return "零食"
    return "混合菜"
