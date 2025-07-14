"""Rule-based food calorie estimation for personalized decision support."""
import logging

logger = logging.getLogger(__name__)

FOOD_ESTIMATES: dict[str, dict] = {
    "冒菜": {"typical": 700, "min": 500, "max": 900, "protein": 30, "carbs": 55, "fat": 35, "risk_tags": ["高油", "高钠", "脂肪偏高"], "portion_advice": "选小份，少油少汤，多蔬菜和瘦肉",
        "context_risks": {"late_night": "临睡前不建议重油重辣", "morning": "不太适合作为早餐"},"better_choices": ["少油少汤", "多蔬菜豆制品", "瘦肉"],"avoid_choices": ["重油重辣", "丸子", "肥牛"]},
    "麻辣烫": {"typical": 650, "min": 450, "max": 850, "protein": 28, "carbs": 50, "fat": 30, "risk_tags": ["高油", "高钠", "取决于配菜"], "portion_advice": "选清汤底，多蔬菜和豆制品，少丸子肥牛",
        "context_risks": {"late_night": "临睡前不建议重油重辣", "morning": "不太适合作为早餐"},"better_choices": ["清汤底", "多蔬菜", "豆制品", "瘦肉"],"avoid_choices": ["重油汤底", "丸子", "肥牛"]},
    "火锅": {"typical": 900, "min": 700, "max": 1400, "protein": 40, "carbs": 40, "fat": 55, "risk_tags": ["高油", "高钠", "容易超量"], "portion_advice": "清汤锅底，多蔬菜瘦肉，控制蘸料和饮品",
        "context_risks": {"late_night": "夜间不建议重油锅底", "morning": "不适合作为早餐"},"better_choices": ["清汤锅", "瘦肉", "蔬菜", "少蘸料"],"avoid_choices": ["牛油锅底", "肥牛", "丸子", "大量蘸料"]},
    "炸鸡": {"typical": 800, "min": 600, "max": 1100, "protein": 35, "carbs": 45, "fat": 50, "risk_tags": ["高脂", "高热量", "油炸"], "portion_advice": "最多 2-3 块，搭配蔬菜，避免额外主食",
        "context_risks": {"late_night": "临睡前不建议高脂油炸", "morning": "不适合作为早餐"},"better_choices": ["小份", "去皮", "搭配蔬菜"],"avoid_choices": ["大份", "加薯条", "加饮料"]},
    "奶茶": {"typical": 450, "min": 250, "max": 700, "protein": 5, "carbs": 55, "fat": 18, "risk_tags": ["高糖", "液体热量", "可能含咖啡因"], "portion_advice": "选无糖或少糖、中杯，避免加料",
        "context_risks": {"late_night": "临睡前不建议含糖/含咖啡因饮品"},"better_choices": ["无糖", "三分糖", "中杯", "不加料"],"avoid_choices": ["全糖", "大杯", "加奶盖", "加珍珠"]},
    "烧烤": {"typical": 900, "min": 600, "max": 1300, "protein": 40, "carbs": 30, "fat": 60, "risk_tags": ["高油", "高盐", "高热量"], "portion_advice": "少油脂部位，多蔬菜串，少蘸料",
        "context_risks": {"late_night": "夜宵不太建议重油重盐烧烤", "morning": "不适合作为早餐"},"better_choices": ["瘦肉串", "鸡胸肉", "烤蔬菜", "少油少辣"],"avoid_choices": ["五花肉", "烤肠", "油炸串", "重油蘸料"]},
    "汉堡": {"typical": 600, "min": 450, "max": 850, "protein": 25, "carbs": 45, "fat": 32, "risk_tags": ["高脂", "精制碳水"], "portion_advice": "单层汉堡 + 沙拉，不加薯条饮料"},
    "沙拉": {"typical": 350, "min": 200, "max": 600, "protein": 20, "carbs": 25, "fat": 18, "risk_tags": ["取决于酱料"], "portion_advice": "酱料减半或选油醋汁"},
    "披萨": {"typical": 750, "min": 500, "max": 1000, "protein": 25, "carbs": 65, "fat": 35, "risk_tags": ["高碳水", "高脂"], "portion_advice": "最多 2-3 片，搭配蔬菜沙拉"},
    "面条": {"typical": 500, "min": 350, "max": 750, "protein": 15, "carbs": 70, "fat": 15, "risk_tags": ["高碳水", "汤底含油"], "portion_advice": "小碗面，少喝汤，搭配蛋白质"},
    "盖饭": {"typical": 650, "min": 500, "max": 900, "protein": 25, "carbs": 70, "fat": 25, "risk_tags": ["高碳水", "浇头含油"], "portion_advice": "少米饭，多要蔬菜浇头"},
    "米饭": {"typical": 260, "min": 200, "max": 350, "protein": 5, "carbs": 58, "fat": 1, "risk_tags": [], "portion_advice": "控制份量，搭配蔬菜和蛋白质"},
    "甜品": {"typical": 400, "min": 250, "max": 600, "protein": 5, "carbs": 50, "fat": 20, "risk_tags": ["高糖", "高热量"], "portion_advice": "饭后小份分享，非正餐替代",
        "context_risks": {"late_night": "临睡前不建议高糖食物"}},
    "零食": {"typical": 300, "min": 150, "max": 500, "protein": 5, "carbs": 30, "fat": 18, "risk_tags": ["高热量密度", "低营养"], "portion_advice": "小包装控制份量"},
}


def estimate_food_for_decision(food_name: str) -> dict:
    """Look up a food by name for estimated nutrition data."""
    for key, data in FOOD_ESTIMATES.items():
        if key in food_name:
            return {"food_name": key, **data}
    # Fallback to generic estimation before returning None
    generic = estimate_generic_food(food_name)
    if generic["typical"] is not None:
        logger.info("assistant_food_estimator: generic match for %s → category=%s", food_name, generic.get("category", "unknown"))
        return generic
    logger.info("assistant_food_estimator: no match for %s", food_name)
    return {
        "food_name": food_name,
        "typical": None, "min": None, "max": None,
        "protein": None, "carbs": None, "fat": None,
        "risk_tags": [], "portion_advice": "建议拍照记录后再精确估算",
    }


# ── Generic food/drink category fallbacks ──

GENERIC_FOOD_CATEGORIES: list[dict] = [
    {
        "clues": {"奶", "快线", "乳饮料", "早餐奶", "旺仔", "AD钙", "养乐多", "益力多"},
        "category": "含糖乳饮料",
        "typical": 280, "min": 180, "max": 400,
        "protein": 6, "carbs": 35, "fat": 8,
        "risk_tags": ["含糖饮料", "液体热量", "饱腹感较弱"],
        "portion_advice": "建议小瓶或半瓶（约250ml），优先选择无糖/低糖替代品",
        "context_risks": {"late_night": "临睡前不建议含糖饮品"},
        "better_choices": ["无糖酸奶", "纯牛奶", "无糖豆浆"],
        "avoid_choices": ["大瓶装", "额外加糖"],
    },
    {
        "clues": {"奶茶", "阿萨姆", "茶饮", "奶盖", "芝士茶"},
        "category": "奶茶/含糖茶饮",
        "typical": 450, "min": 300, "max": 700,
        "protein": 5, "carbs": 55, "fat": 18,
        "risk_tags": ["高糖", "液体热量", "可能含咖啡因"],
        "portion_advice": "选中杯、无糖或少糖，不加奶盖和珍珠",
        "context_risks": {"late_night": "临睡前不建议含糖/含咖啡因饮品"},
        "better_choices": ["无糖", "三分糖", "中杯", "不加料"],
        "avoid_choices": ["全糖", "大杯", "加奶盖", "加珍珠"],
    },
    {
        "clues": {"咖啡", "拿铁", "美式", "摩卡", "卡布奇诺", "冷萃", "澳白", "flat white", "latte"},
        "category": "咖啡饮品",
        "typical": 150, "min": 5, "max": 350,
        "protein": 6, "carbs": 10, "fat": 7,
        "risk_tags": ["咖啡因", "加糖款热量高"],
        "portion_advice": "美式/冷萃接近0热量；拿铁/摩卡注意牛奶和糖浆",
        "context_risks": {"late_night": "临睡前不建议摄入咖啡因"},
        "better_choices": ["美式（无糖）", "冷萃", "脱脂拿铁", "小杯"],
        "avoid_choices": ["摩卡", "焦糖玛奇朵", "奶油顶", "大杯加糖"],
    },
    {
        "clues": {"可乐", "雪碧", "汽水", "碳酸", "芬达", "苏打水", "气泡水"},
        "category": "碳酸饮料/气泡饮品",
        "typical": 150, "min": 0, "max": 260,
        "protein": 0, "carbs": 38, "fat": 0,
        "risk_tags": ["含糖饮料", "液体热量", "无营养"],
        "portion_advice": "无糖版接近0 kcal；含糖版一瓶约150-250 kcal",
        "better_choices": ["无糖可乐", "苏打水", "气泡水（无糖）"],
        "avoid_choices": ["含糖汽水", "大瓶装"],
    },
    {
        "clues": {"果汁", "橙汁", "苹果汁", "西瓜汁", "蔬菜汁"},
        "category": "果汁/蔬菜汁",
        "typical": 180, "min": 100, "max": 300,
        "protein": 1, "carbs": 40, "fat": 0,
        "risk_tags": ["液体热量", "易被忽略", "糖分集中"],
        "portion_advice": "小杯（200-300ml），整果比果汁更饱腹",
        "better_choices": ["小杯", "不加糖", "鲜榨（少喝汁、多吃整果）"],
        "avoid_choices": ["大杯", "加糖", "浓缩还原"],
    },
    {
        "clues": {"茶", "绿茶", "红茶", "乌龙", "普洱", "花茶", "东方树叶", "三得利", "无糖茶"},
        "category": "茶饮（无糖/低糖）",
        "typical": 5, "min": 0, "max": 30,
        "protein": 0, "carbs": 0, "fat": 0,
        "risk_tags": ["咖啡因（部分）"],
        "portion_advice": "东方树叶等无糖茶接近0 kcal，是很好的日常饮品",
        "better_choices": ["无糖茶", "淡茶"],
    },
    {
        "clues": {"面包", "吐司", "可颂", "牛角包", "达利园", "好丽友"},
        "category": "面包/烘焙食品",
        "typical": 300, "min": 150, "max": 500,
        "protein": 8, "carbs": 45, "fat": 10,
        "risk_tags": ["容易低估", "饱腹感不稳定", "高碳水", "可能含糖油"],
        "portion_advice": "注意份量和配料表，夹心/涂酱款热量翻倍",
        "context_risks": {"morning": "早餐可以吃，搭配蛋白质更均衡"},
        "better_choices": ["全麦面包", "无夹心款", "搭配鸡蛋/牛奶"],
        "avoid_choices": ["奶油夹心", "巧克力涂层", "大份"],
    },
    {
        "clues": {"饼干", "曲奇", "威化", "薯片", "薯条", "虾条"},
        "category": "饼干/零食",
        "typical": 350, "min": 200, "max": 550,
        "protein": 5, "carbs": 45, "fat": 18,
        "risk_tags": ["高热量密度", "低营养", "容易吃多"],
        "portion_advice": "小包装约30-50g，注意不要整包吃完",
        "context_risks": {"late_night": "临睡前不建议高热量零食"},
        "better_choices": ["小包装", "苏打饼干", "水果替代"],
        "avoid_choices": ["大包装", "奶油夹心"],
    },
    {
        "clues": {"泡面", "方便面", "拉面说", "酸辣粉", "螺蛳粉"},
        "category": "方便面/速食面",
        "typical": 500, "min": 350, "max": 700,
        "protein": 12, "carbs": 60, "fat": 22,
        "risk_tags": ["高钠", "高油", "高碳水", "低蛋白"],
        "portion_advice": "少喝汤（汤里钠和油最多），可以加鸡蛋和蔬菜",
        "context_risks": {"late_night": "夜宵不建议高钠高油速食面"},
        "better_choices": ["煮面（少放调料包）", "加蔬菜和蛋白质"],
        "avoid_choices": ["全料包", "喝完汤", "加火腿肠"],
    },
    {
        "clues": {"鸡蛋", "水煮蛋", "煎蛋", "炒蛋"},
        "category": "鸡蛋",
        "typical": 150, "min": 70, "max": 200,
        "protein": 13, "carbs": 1, "fat": 10,
        "risk_tags": [],
        "portion_advice": "1-2个水煮蛋作为加餐或正餐一部分，营养密度高",
        "better_choices": ["水煮蛋", "蒸蛋", "少油煎蛋"],
    },
    {
        "clues": {"鸡胸肉", "鸡腿", "鸡翅"},
        "category": "鸡肉",
        "typical": 200, "min": 100, "max": 350,
        "protein": 30, "carbs": 0, "fat": 8,
        "risk_tags": [],
        "portion_advice": "鸡胸是很好的减脂期蛋白质来源，去皮更佳",
        "better_choices": ["鸡胸肉", "去皮", "清蒸/水煮"],
        "avoid_choices": ["炸鸡", "鸡皮", "酱料过多"],
    },
    {
        "clues": {"牛肉", "牛排", "牛腩", "肥牛"},
        "category": "牛肉",
        "typical": 250, "min": 150, "max": 450,
        "protein": 26, "carbs": 0, "fat": 15,
        "risk_tags": ["注意部位（肥牛脂肪偏高）"],
        "portion_advice": "瘦牛肉是优质蛋白质；肥牛/牛腩脂肪偏高，适量。",
        "better_choices": ["瘦牛肉", "里脊", "腱子"],
        "avoid_choices": ["肥牛", "牛腩（大份）", "油炸牛肉"],
    },
    {
        "clues": {"水果", "苹果", "香蕉", "橘子", "草莓", "蓝莓", "西瓜", "葡萄"},
        "category": "水果",
        "typical": 100, "min": 50, "max": 200,
        "protein": 1, "carbs": 25, "fat": 0,
        "risk_tags": [],
        "portion_advice": "一份水果约一个拳头大小；作为加餐比零食健康",
        "better_choices": ["新鲜水果", "适量（1-2份/天）"],
        "avoid_choices": ["果干（热量集中）", "果汁", "大量高糖水果"],
    },
]


def estimate_generic_food(food_name: str) -> dict:
    """Match food/drink name to a generic category using clue keywords.

    Returns a dict with estimated nutrition data, or typical=None if no match.
    """
    for cat in GENERIC_FOOD_CATEGORIES:
        clues: set = cat.get("clues", set())
        if any(c in food_name for c in clues):
            result = {"food_name": food_name, "generic_match": True, **cat}
            # Don't expose internal keys to callers expecting the standard format
            result.pop("clues", None)
            return result
    return {
        "food_name": food_name,
        "typical": None, "min": None, "max": None,
        "protein": None, "carbs": None, "fat": None,
        "risk_tags": [], "portion_advice": "建议拍照记录后再精确估算",
    }
