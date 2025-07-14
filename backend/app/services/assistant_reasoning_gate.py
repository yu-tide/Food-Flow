"""Agentic reasoning gate — classifies user intent before any data fetching or LLM call.

This module runs synchronously (no I/O) and returns an AssistantReasoningResult
that the rest of the pipeline uses for dispatch, tool selection, and validation.
"""
import logging
import re

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Reasoning result model
# ═══════════════════════════════════════════════════════════════

class AssistantReasoningResult(BaseModel):
    request_type: str
    decision_mode: str
    should_use_user_data: bool = False
    should_use_rag: bool = False
    should_suggest_action: bool = False
    should_refuse_or_limit: bool = False
    needs_clarification: bool = False
    required_tools: list[str] = []
    answer_strategy: str = ""
    user_visible_constraints: list[str] = []
    hidden_constraints: list[str] = []
    risk_level: str = "low"


# ═══════════════════════════════════════════════════════════════
# Keyword sets
# ═══════════════════════════════════════════════════════════════

GREETINGS = {"你好", "hi", "hello", "在吗", "你是谁", "你能做什么", "你能干什么", "你会什么"}

RECORD_KEYWORDS = {"这顿饭", "这条记录", "这个记录", "当前记录", "脂肪是否偏高", "成分", "校准", "重量", "调整成分"}
RECENT_KEYWORDS = {"最近", "哪几顿", "高热量", "高脂肪", "脂肪偏高", "蛋白质最高", "热量最高"}
WEEKLY_KEYWORDS = {"本周", "这周", "周统计", "蛋白质达标", "这一周", "这周哪天"}
TODAY_KEYWORDS = {"今天", "今日", "今天吃得", "今日摄入", "今天摄入", "今天吃了"}
SETTINGS_KEYWORDS = {"目标", "热量目标", "蛋白质目标", "怎么设置目标"}

KNOWLEDGE_KEYWORDS = {
    "怎么吃", "原理", "区别", "减脂", "增肌",
    "冒菜", "麻辣烫", "火锅", "未保存记录", "统计规则",
    "蛋白质", "碳水", "脂肪", "营养", "维生素", "矿物质",
    "为什么", "作用", "功能", "液体热量", "是什么",
}
DATA_INTENT_KEYWORDS = {
    "今天", "今日", "本周", "这周", "最近",
    "这顿饭", "当前记录", "蛋白质达标", "热量最高",
}

FOOD_NAMES = {
    "冒菜", "麻辣烫", "火锅", "炸鸡", "奶茶", "烧烤",
    "汉堡", "披萨", "面条", "米饭", "盖饭", "沙拉", "甜品", "零食",
}

FOOD_DECISION_KEYWORDS = {
    "可以吃吗", "能吃吗", "适合吗", "怎么样", "会不会超标", "要不要吃",
    "吃多少", "点什么", "怎么点", "推荐吗", "中午吃", "晚上吃", "今天吃",
    "现在吃", "能喝吗", "喝奶茶", "吃这个", "吃顿",
    "可以吃", "能吃", "能喝", "可以喝", "能不能吃", "能不能喝",
    "想吃", "想喝", "该不该吃", "该不该喝",
}

MEAL_PLAN_KEYWORDS = {
    "夜宵方案", "制定夜宵", "夜宵推荐", "夜宵吃什么",
    "晚餐方案", "晚餐推荐", "早餐方案", "早餐推荐", "午餐方案", "午餐推荐",
    "今天吃什么", "今天吃点什么", "推荐吃点什么", "帮我安排一餐",
    "减脂夜宵", "低脂夜宵", "清淡夜宵",
    "帮我制定", "饮食方案", "一餐建议",
    "夜宵", "方案",
}

VAGUE_KEYWORDS = {"这个怎么看", "这里怎么回事", "帮我分析", "这个正常吗", "怎么看", "什么意思", "怎么办"}

# ── Forbidden action patterns ──
FORBIDDEN_ACTION_PATTERNS = [
    r"删除所有", r"清空所有", r"清空数据", r"清除所有",
    r"自动确认", r"自动.*确认",
    r"直接改", r"直接.*修改", r"直接.*删除",
    r"删除.*所有.*记录", r"清除.*记录", r"帮.*删除",
    r"把.*目标.*改成", r"帮.*改.*目标", r"帮.*改.*设置",
    r"帮.*修改.*记录", r"帮.*修改.*热量", r"帮.*修改.*成分",
]

# ── Safe action patterns ──
SAFE_ACTION_PATTERNS = [
    "打开设置", "保存当前", "保存这顿", "确认这顿",
    "生成周报", "导出周报", "导出本周", "生成报告",
    "这周报告", "查看详情", "打开记录", "去设置",
    "调整目标", "修改我的目标",
]

# ── Product rule patterns ──
PRODUCT_RULE_PATTERNS = [
    r"为什么未保存", r"为什么.*不进统计", r"菜名候选",
    r"统计规则", r"如何调整成分", r"AI 分析偏好",
    r"未保存.*进入统计", r"draft", r"processing",
    r"为什么.*没有记录",
]

# ── Domain scope ──
FOODFLOW_DOMAIN_KEYWORDS = {
    "饮食", "吃", "喝", "餐", "早餐", "午餐", "晚餐", "夜宵",
    "食物", "食品", "菜", "饭", "热量", "卡路里", "蛋白质", "碳水", "脂肪",
    "减脂", "增肌", "维持", "营养", "目标", "体重",
    "记录", "上传", "图片", "识别", "菜名", "成分", "重量",
    "周报", "统计", "设置", "FoodFlow", "AI分析",
    "确认", "保存", "未保存", "已保存", "餐图", "摄入", "消耗",
    "食谱", "饮食方案",
}
# NOTE: time words (今天/本周/最近) and common verbs (能/可以/怎么/为什么) are deliberately
# excluded — they are handled by priority routing, not domain keywords.

# ── Drink entity clues ──
DRINK_CLUES = {
    "奶", "茶", "咖啡", "拿铁", "美式", "果汁", "可乐", "雪碧",
    "饮料", "乳饮料", "酸奶", "豆浆", "牛奶", "酒", "啤酒", "水", "汤",
    "快线", "冰红茶", "绿茶", "红茶", "乌龙", "普洱", "花茶",
    "苏打水", "气泡水", "运动饮料",
}

# ── Food entity clues ──
FOOD_CLUES = {
    "饭", "面", "粉", "饼", "包", "肉", "鸡", "鱼", "蛋", "菜", "粥",
    "沙拉", "汉堡", "披萨", "火锅", "烧烤", "麻辣烫", "冒菜",
    "炸鸡", "零食", "甜品", "蛋糕", "饼干", "薯片", "泡面",
    "面包", "巧克力", "饺子", "馄饨", "馒头", "花卷",
}

# ── Food/drink intent verbs ──
FOOD_VERB_CLUES = {"吃", "喝", "尝", "试", "点", "买", "叫", "要"}

# ── Daily history: date expressions + food data semantics ──
DAILY_DATE_PATTERNS = [
    (r"昨天", "昨天"),
    (r"前天", "前天"),
    (r"大前天", "大前天"),
    (r"上周一", "上周一"), (r"上周二", "上周二"), (r"上周三", "上周三"),
    (r"上周四", "上周四"), (r"上周五", "上周五"), (r"上周六", "上周六"), (r"上周日", "上周日"),
    # Chinese month-day: 5月16, 5月16日, 5月16号 (日/号 optional)
    (r"\d{1,2}月\d{1,2}(?:[日号])?", "指定日期"),
    # Dot format: 5.16, 05.16
    (r"\d{1,2}\.\d{1,2}", "指定日期"),
    # Dash format: 5-16, 2026-05-16
    (r"\d{4}-\d{1,2}-\d{1,2}", "指定日期"),
    (r"\d{1,2}-\d{1,2}", "指定日期"),
    # Weekday
    (r"星期[一二三四五六日天]", "本周"),
]
DAILY_FOOD_SEMANTICS = {
    "摄入", "热量", "卡路里", "蛋白质", "碳水", "脂肪",
    "吃了", "吃了多少", "有没有记录", "有没有饮食", "超标",
    "记录", "饮食记录", "统计", "营养",
    "吃的怎么样", "吃得怎么样", "饮食怎么样", "吃得好吗",
    "饮食情况", "饮食总结", "营养怎么样", "吃得健康吗",
    "控制得怎么样", "饮食健康吗", "吃得如何",
    "饮食",  # catch-all for "饮食" in date context
}

def _detect_date_expression(msg: str) -> tuple[str | None, str | None]:
    """Detect natural-language date expressions in a message.
    Returns (date_expr, date_label) or (None, None).
    Rule: only trigger if there's ALSO food data semantics in the message.
    """
    for pattern, label in DAILY_DATE_PATTERNS:
        if re.search(pattern, msg):
            return (re.search(pattern, msg).group(0), label)
    return (None, None)

# ── Food decision semantic patterns ──
FOOD_DECISION_SEMANTIC_PATTERNS = [
    r"想[吃喝和尝试点买叫要]",
    r"想要[吃喝和]",
    r"想来点",
    r"想吃点", r"喝点",
    r"馋", r"有点饿",
    r"能[吃喝和]吗",
    r"可以[吃喝和]吗",
    r"能不能[吃喝和]",
    r"该不该[吃喝和]",
    r"适合[吃喝和]吗",
    r"要不要[吃喝和]",
    r"会不会超标",
    r"今天还能[吃喝和]",
    r"现在能不能[吃喝和]",
    r"(?:现在|早上|上午|中午|下午|晚上|夜宵|睡前|运动后).{0,4}[吃喝和]",
    r"(?:减脂期|增肌期|控糖|低脂|低碳).{0,3}[能吃能喝可以吃可以喝]",
]

# ── Typos → correct ──
TYPO_FIXES = [
    (r"想和(?!谐|平|解|好|睦|气|你)", "想喝"),
    (r"能和(?!谐|平|解|好|睦|气|你|力|够)", "能喝"),
    (r"可以和(?!谐|平|解|好|睦|气|你)", "可以喝"),
    (r"今天还能和(?!谐|平|解|好|睦|气|你)", "今天还能喝"),
]


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _match_any(msg: str, keywords: set) -> bool:
    return any(kw in msg for kw in keywords)


def _match_any_pattern(msg: str, patterns: list[str]) -> bool:
    return any(re.search(p, msg) for p in patterns)


def normalize_user_message(message: str) -> str:
    """Fix common typos in food/drink intent messages."""
    result = message
    for pattern, replacement in TYPO_FIXES:
        if re.search(pattern, result):
            new_result = re.sub(pattern, replacement, result)
            if new_result != result:
                logger.warning("TRACE_REASONING_NORMALIZED original=%s normalized=%s", result, new_result)
                result = new_result
                break  # one fix per message
    return result


def detect_food_or_drink_entity(message: str) -> dict:
    """Detect food/drink entities in a message using clues + context patterns.

    Returns:
        {has_entity, entity_text, entity_type: "food"|"drink"|"unknown", confidence, reason}
    """
    msg = message.strip()

    # 1. Check explicit food/drink clues
    drink_matches = [c for c in DRINK_CLUES if c in msg]
    food_matches = [c for c in FOOD_CLUES if c in msg]

    # 2. Check for verb + noun phrase pattern: e.g. "想喝营养快线", "吃泡面"
    entity_text = ""
    entity_type = "unknown"
    confidence = "low"

    # Pattern: verb (吃/喝/想+V) followed by 2-12 char noun phrase
    verb_pattern = re.compile(r"(?:想[吃喝和]|[吃喝和]|想吃|想喝|吃点|喝点)\s*([一-鿿\w]{2,12})")
    match = verb_pattern.search(msg)
    if match:
        candidate = match.group(1)
        # Filter out non-food words
        noise = {"了吗", "什么", "怎么", "多少", "能不能", "可以吗", "怎么样", "会不会", "要不要", "该不该", "得怎么样", "了多少", "了什么", "什么样的", "什么东西", "干嘛", "的怎么样", "吃得怎么样", "吃的怎么样", "摄入多少", "热量多少", "饮食怎么样", "有没有记录", "有没有超标"}
        if candidate not in noise and not candidate.startswith("吗") and not candidate.startswith("怎么样") and not candidate.startswith("得") and not candidate.startswith("的"):
            entity_text = candidate
            # Determine type from clues
            has_drink_clue = any(c in candidate for c in DRINK_CLUES)
            has_food_clue = any(c in candidate for c in FOOD_CLUES)
            if has_drink_clue and not has_food_clue:
                entity_type = "drink"
                confidence = "medium"
            elif has_food_clue and not has_drink_clue:
                entity_type = "food"
                confidence = "medium"
            elif has_drink_clue:
                entity_type = "drink"
                confidence = "low"
            elif has_food_clue:
                entity_type = "food"
                confidence = "low"
            else:
                # Unknown but has verb+noun pattern — still a candidate
                entity_type = "unknown"
                confidence = "low"

    # 3. If no verb pattern but has standalone food/drink clues
    if not entity_text:
        if drink_matches and not food_matches:
            entity_text = drink_matches[0]
            entity_type = "drink"
            confidence = "low"
        elif food_matches and not drink_matches:
            entity_text = food_matches[0]
            entity_type = "food"
            confidence = "low"
        elif drink_matches or food_matches:
            entity_text = (drink_matches + food_matches)[0]
            entity_type = "drink" if len(drink_matches) >= len(food_matches) else "food"
            confidence = "low"

    has_entity = bool(entity_text)
    reason = (
        f"verb+noun pattern matched '{entity_text}'" if match and entity_text
        else f"clue-matched '{entity_text}'" if entity_text
        else "no food/drink entity detected"
    )

    logger.warning("TRACE_FOOD_ENTITY_DETECTION has_entity=%s entity=%s type=%s confidence=%s",
                   has_entity, entity_text, entity_type, confidence)

    return {"has_entity": has_entity, "entity_text": entity_text,
            "entity_type": entity_type, "confidence": confidence, "reason": reason}


def is_food_decision_semantic(message: str, entity: dict) -> bool:
    """Check if message has food decision intent (want/eat/can/decision patterns).

    Must be called with result from detect_food_or_drink_entity().
    """
    if not entity["has_entity"]:
        return False

    msg = message.strip()
    entity_text = entity.get("entity_text", "")

    # 1. Explicit decision patterns
    if _match_any_pattern(msg, FOOD_DECISION_SEMANTIC_PATTERNS):
        logger.warning("TRACE_FOOD_DECISION_SEMANTIC result=true reason=explicit_pattern")
        return True

    # 2. Implicit: food/drink name + time context
    time_triggers = {"现在", "早上", "上午", "中午", "下午", "晚上", "夜宵", "睡前", "饭后", "饭前", "运动后"}
    has_time = any(t in msg for t in time_triggers)
    if has_time and entity_text:
        logger.warning("TRACE_FOOD_DECISION_SEMANTIC result=true reason=time+entity")
        return True

    # 3. Implicit: food/drink name + goal context
    goal_triggers = {"减脂期", "增肌期", "控糖", "低脂", "低碳", "减重", "刷脂"}
    has_goal = any(t in msg for t in goal_triggers)
    if has_goal and entity_text:
        logger.warning("TRACE_FOOD_DECISION_SEMANTIC result=true reason=goal+entity")
        return True

    # 4. Implicit: food/drink name + "吗" or "怎么样" or "能不能" or "可以"
    question_markers = {"吗", "怎么样", "能不能", "可以不", "可以吗", "适合吗"}
    has_question = any(m in msg for m in question_markers)
    if has_question and entity_text:
        logger.warning("TRACE_FOOD_DECISION_SEMANTIC result=true reason=question+entity")
        return True

    logger.warning("TRACE_FOOD_DECISION_SEMANTIC result=false reason=no_pattern_matched")
    return False


def is_in_domain(message: str) -> bool:
    """Whitelist-first domain check: is this message within FoodFlow's scope?

    True if: matches domain keywords, OR is a greeting/assistant intro.
    False if: clearly out of domain with no domain keywords.
    """
    msg = message.strip()

    # Always allow high-priority intents already matched (food_decision, meal_plan, etc.)
    # This function is only called for unmatched messages falling to out_of_scope/general_chat.

    # Check domain keywords
    if _match_any(msg, FOODFLOW_DOMAIN_KEYWORDS):
        return True

    # Check if message has food/drink entity
    entity = detect_food_or_drink_entity(msg)
    if entity["has_entity"]:
        return True

    # Check for food-related verb usage (吃/喝/餐 etc.)
    food_verbs = {"吃", "喝", "餐", "菜", "饭", "营养", "热量", "卡路里"}
    if any(v in msg for v in food_verbs):
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# Main classifier
# ═══════════════════════════════════════════════════════════════

def build_reasoning_result(
    message: str,
    page: str = "",
    page_context: dict | None = None,
) -> AssistantReasoningResult:
    """Classify user message into request_type + decision_mode BEFORE any data fetching."""
    raw_msg = message.strip()
    ctx = page_context or {}

    # Normalize typos before classification
    msg = normalize_user_message(raw_msg)

    # ── Priority 1: Forbidden action ──
    if _match_any_pattern(msg, FORBIDDEN_ACTION_PATTERNS):
        logger.warning("TRACE_REASONING_RESULT request_type=forbidden_action decision_mode=refuse_unsafe")
        return AssistantReasoningResult(
            request_type="forbidden_action",
            decision_mode="refuse_unsafe",
            should_refuse_or_limit=True,
            risk_level="high",
            answer_strategy="明确拒绝直接修改/删除操作，解释原因，引导用户使用页面安全操作路径",
            user_visible_constraints=["不支持自动删除或修改数据"],
            hidden_constraints=["no_data_fetch", "no_llm_call", "no_suggested_actions"],
        )

    # ── Priority 2: Safe action (before food_decision to catch "帮我保存" on confirm page) ──
    if _match_any(msg, set(SAFE_ACTION_PATTERNS)):
        is_confirm_page = page.startswith("/confirm/")
        if is_confirm_page and any(kw in msg for kw in ("保存", "确认", "帮我保存")):
            logger.warning("TRACE_REASONING_RESULT request_type=safe_action decision_mode=action_confirmation")
            return AssistantReasoningResult(
                request_type="safe_action", decision_mode="action_confirmation",
                should_suggest_action=True, risk_level="medium",
                answer_strategy="简短确认动作，让用户确认后执行",
            )
        logger.warning("TRACE_REASONING_RESULT request_type=safe_action decision_mode=action_confirmation")
        return AssistantReasoningResult(
            request_type="safe_action", decision_mode="action_confirmation",
            should_suggest_action=True, risk_level="low",
            answer_strategy="简短确认动作，让用户确认后执行",
        )

    # ── Priority 2.5: Daily history (yesterday/date + food semantics) — BEFORE food_decision ──
    date_expr, date_label = _detect_date_expression(msg)
    if date_expr:
        has_food_semantics = _match_any(msg, DAILY_FOOD_SEMANTICS)
        has_non_food = _match_any(msg, {"股市", "股票", "天气", "新闻", "比赛", "考试", "游戏", "电影"})
        if has_food_semantics and not has_non_food:
            logger.warning("TRACE_REASONING_RESULT request_type=daily_history decision_mode=data_driven_advice date_expr=%s date_label=%s",
                           date_expr, date_label)
            return AssistantReasoningResult(
                request_type="daily_history", decision_mode="data_driven_advice",
                should_use_user_data=True,
                required_tools=["daily_snapshot", "user_settings", "time_context"],
                risk_level="low",
                answer_strategy=f"查询{date_label}的已保存饮食记录，只统计已保存记录。如果记录数>0，直接回答统计结果，禁止建议用户去页面查看或说系统不能查历史。如果记录数为0，明确说明该日期无已保存记录，摄入为0 kcal，不要编造正数摄入。",
                user_visible_constraints=["仅统计已保存记录", f"查询日期: {date_label}"],
                hidden_constraints=["validate_numbers", "no_fabrication_when_zero"],
            )

    # ── Priority 3: Food decision (semantic + entity-based) ──
    entity = detect_food_or_drink_entity(msg)
    is_food_dec = is_food_decision_semantic(msg, entity)

    # Also keep old keyword-based matching for backward compat
    has_food_kw = _match_any(msg, FOOD_NAMES)
    has_decision_kw = _match_any(msg, FOOD_DECISION_KEYWORDS)
    old_match = (has_food_kw and has_decision_kw)

    if is_food_dec or old_match:
        logger.warning("TRACE_REASONING_RESULT request_type=food_decision decision_mode=cautious_advice")
        return AssistantReasoningResult(
            request_type="food_decision",
            decision_mode="cautious_advice",
            should_use_user_data=True,
            required_tools=["dashboard_snapshot", "user_settings", "recent_records", "time_context", "food_estimate"],
            risk_level="medium",
            answer_strategy="综合时间+热量+食物风险+最近饮食判断是否适合吃/喝。不能只看热量，时间不合适时必须先判断再建议。",
            user_visible_constraints=["根据已保存记录判断"],
            hidden_constraints=["no_raw_internal_fields", "validate_numbers"],
        )

    # ── Priority 4: Meal plan ──
    if _match_any(msg, MEAL_PLAN_KEYWORDS):
        is_late = bool(re.search(r"夜宵|深夜|晚上|睡前|睡觉|快睡觉", msg))
        decision_mode = "cautious_advice" if is_late else "data_driven_advice"
        logger.warning("TRACE_REASONING_RESULT request_type=meal_plan decision_mode=%s", decision_mode)
        return AssistantReasoningResult(
            request_type="meal_plan", decision_mode=decision_mode,
            should_use_user_data=True,
            required_tools=["dashboard_snapshot", "user_settings", "recent_records", "time_context"],
            risk_level="low",
            answer_strategy=(
                "深夜优先低脂、清淡、小份、好消化，不直接给正式一餐建议。先判断是否适合吃，再给轻量选择。"
                if is_late else "根据时间+热量+目标制定一餐建议。"
            ),
            user_visible_constraints=["根据已保存记录判断"],
            hidden_constraints=["no_raw_internal_fields", "validate_numbers"],
        )

    # ── Priority 5: Record analysis ──
    if _match_any(msg, RECORD_KEYWORDS):
        record_id = ctx.get("record_id", "")
        if not record_id:
            logger.warning("TRACE_REASONING_RESULT request_type=record_analysis decision_mode=clarification_needed")
            return AssistantReasoningResult(
                request_type="record_analysis", decision_mode="clarification_needed",
                needs_clarification=True, risk_level="low",
                answer_strategy="追问用户指的是哪条记录，不要胡乱猜测",
                user_visible_constraints=["需要用户指定具体记录"],
            )
        logger.warning("TRACE_REASONING_RESULT request_type=record_analysis decision_mode=information_retrieval")
        return AssistantReasoningResult(
            request_type="record_analysis", decision_mode="information_retrieval",
            should_use_user_data=True, required_tools=["record_detail"], risk_level="low",
            answer_strategy="展示该记录详情和成分，说明保存状态",
        )

    # ── Priority 6.1: Dashboard summary (domain-guarded) ──
    if _match_any(msg, TODAY_KEYWORDS):
        # Only dashboard_summary if the message is actually about FoodFlow
        if is_in_domain(msg):
            logger.warning("TRACE_REASONING_RESULT request_type=dashboard_summary decision_mode=data_driven_advice")
            return AssistantReasoningResult(
                request_type="dashboard_summary", decision_mode="data_driven_advice",
                should_use_user_data=True, required_tools=["dashboard_snapshot"], risk_level="low",
                answer_strategy="总结今日已保存数据，record_count==0 时说明今天无已保存记录",
                user_visible_constraints=["仅统计已保存记录"],
                hidden_constraints=["validate_numbers"],
            )
        # "今天" present but not domain → let it fall through (will hit general_chat guard or out_of_scope)
        logger.warning("TRACE_REASONING_RESULT request_type=dashboard_summary SKIPPED (not in domain)")

    # ── Priority 6.2: Weekly analysis ──
    if _match_any(msg, WEEKLY_KEYWORDS):
        logger.warning("TRACE_REASONING_RESULT request_type=weekly_analysis decision_mode=data_driven_advice")
        return AssistantReasoningResult(
            request_type="weekly_analysis", decision_mode="data_driven_advice",
            should_use_user_data=True, required_tools=["weekly_snapshot"], risk_level="low",
            answer_strategy="总结本周已保存统计，日均+总览，只统计已保存记录",
            user_visible_constraints=["仅统计已保存记录"],
        )

    # ── Priority 7: Settings advice ──
    if _match_any(msg, SETTINGS_KEYWORDS):
        logger.warning("TRACE_REASONING_RESULT request_type=settings_advice decision_mode=data_driven_advice")
        return AssistantReasoningResult(
            request_type="settings_advice", decision_mode="data_driven_advice",
            should_use_user_data=True, required_tools=["user_settings"], risk_level="low",
            answer_strategy="展示当前目标，解释如何调整，可以引导去设置页，但不能声称已修改。",
            user_visible_constraints=["不直接修改设置，引导用户前往设置页面"],
        )

    # ── Priority 8: Nutrition knowledge vs product rule ──
    has_knowledge = _match_any(msg, KNOWLEDGE_KEYWORDS)
    has_data_intent = _match_any(msg, DATA_INTENT_KEYWORDS)
    should_rag = has_knowledge and not has_data_intent

    # Guard: bare entity (just a food/drink name) without a knowledge question → skip
    # Knowledge questions have: 为什么/怎么/是什么/原理/作用/区别/如何
    is_knowledge_question = bool(re.search(r"为什么|怎么|是什么|原理|作用|区别|如何|热量高吗|热量.*多少", msg))
    if should_rag and entity["has_entity"] and not is_knowledge_question:
        logger.warning("TRACE_REASONING_RESULT skipping priority 8 (bare entity, not a knowledge question)")
        pass  # fall through to general_chat guard
    elif should_rag:
        is_product_rule = _match_any_pattern(msg, PRODUCT_RULE_PATTERNS)
        rt = "product_rule" if is_product_rule else "nutrition_knowledge"
        logger.warning("TRACE_REASONING_RESULT request_type=%s decision_mode=information_retrieval", rt)
        return AssistantReasoningResult(
            request_type=rt, decision_mode="information_retrieval",
            should_use_rag=True, required_tools=["rag_search"], risk_level="low",
            answer_strategy=(
                "解释产品逻辑（如为什么未保存不进统计、菜名候选含义等），不泄漏内部字段"
                if is_product_rule
                else "解释营养原理或食物知识，不涉及具体用户数据，不覆盖真实数据"
            ),
        )

    # ── Priority 9: Greetings / assistant_intro ──
    if msg in GREETINGS or len(msg) <= 3:
        logger.warning("TRACE_REASONING_RESULT request_type=general_chat decision_mode=general_conversation")
        return AssistantReasoningResult(
            request_type="general_chat", decision_mode="general_conversation", risk_level="low",
            answer_strategy="简短介绍 FoodFlow AI 助手的能力范围（饮食记录、营养分析、餐食建议、产品规则），不介绍通用能力",
        )

    # ── Priority 10: General chat guard — don't let food/drink messages fall through ──
    # Check if message has food/drink entity but weak semantic intent
    if entity["has_entity"]:
        # Has entity but no decision intent → ask clarifying question
        logger.warning("TRACE_REASONING_RESULT request_type=general_chat decision_mode=clarification_needed (bare entity)")
        return AssistantReasoningResult(
            request_type="general_chat", decision_mode="clarification_needed",
            needs_clarification=True, risk_level="low",
            answer_strategy=f"追问用户意图：是想问{entity['entity_text']}热量高不高，还是想让我判断现在适不适合吃/喝？",
            user_visible_constraints=["需要追问用户意图"],
        )

    # Check if message has food domain keywords but didn't match any intent
    domain_terms = {"吃", "喝", "餐", "饭", "菜", "热量", "卡路里", "蛋白质", "碳水", "脂肪",
                    "减脂", "增肌", "营养", "体重", "记录", "上传", "图片", "识别",
                    "周报", "统计", "保存", "未保存", "已保存", "摄入", "消耗"}
    if any(t in msg for t in domain_terms):
        # Domain signal detected but no clear intent → ask clarifying question
        logger.warning("TRACE_REASONING_RESULT request_type=general_chat decision_mode=clarification_needed (domain signal)")
        return AssistantReasoningResult(
            request_type="general_chat", decision_mode="clarification_needed",
            needs_clarification=True, risk_level="low",
            answer_strategy="用户提到了饮食/营养相关词汇但意图不明确，追问想了解什么",
            user_visible_constraints=["需要追问用户意图"],
        )

    # ── Priority 11: Out of scope (whitelist-first) ──
    # Only trigger if: NOT in domain AND NOT already matched by above priorities
    if not is_in_domain(msg):
        logger.warning("TRACE_REASONING_RESULT request_type=out_of_scope decision_mode=domain_boundary")
        return AssistantReasoningResult(
            request_type="out_of_scope", decision_mode="domain_boundary",
            should_refuse_or_limit=False, risk_level="low",
            answer_strategy="礼貌说明FoodFlow服务范围，引导用户回到饮食管理问题",
            user_visible_constraints=["不回答与饮食、营养、FoodFlow产品无关的问题"],
            hidden_constraints=["no_data_fetch", "no_llm_call", "no_rag"],
        )

    # ── Priority 12: Recent records ──
    if _match_any(msg, RECENT_KEYWORDS):
        logger.warning("TRACE_REASONING_RESULT request_type=general_chat decision_mode=data_driven_advice")
        return AssistantReasoningResult(
            request_type="general_chat", decision_mode="data_driven_advice",
            should_use_user_data=True, required_tools=["recent_records"], risk_level="low",
            answer_strategy="总结最近已保存记录，热量排序，只统计已保存记录",
        )

    # ── Priority 13: Vague → page-aware fallback ──
    if _match_any(msg, VAGUE_KEYWORDS):
        logger.warning("TRACE_REASONING_RESULT request_type=general_chat decision_mode=general_conversation")
        return AssistantReasoningResult(
            request_type="general_chat", decision_mode="general_conversation", risk_level="low",
            answer_strategy="根据当前页面给出引导性回答，帮助用户了解可以问什么",
        )

    # ── Priority 14: Ultimate fallback ──
    logger.warning("TRACE_REASONING_RESULT request_type=general_chat decision_mode=general_conversation")
    return AssistantReasoningResult(
        request_type="general_chat", decision_mode="general_conversation", risk_level="low",
        answer_strategy="简短介绍或页面引导",
    )
