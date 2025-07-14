"""Assistant LLM service — reuses project Bailian client for natural replies."""
import copy
import json
import logging
import re
import time

from app.core.config import settings
from app.services.assistant_reasoning_gate import AssistantReasoningResult

logger = logging.getLogger(__name__)

# ── Forbidden internal fields (must NEVER reach LLM input or user-facing output) ──

FORBIDDEN_LLM_INPUT_KEYS = {
    "local_hour", "client_time_iso", "timezone",
    "meal_period", "has_known_local_time",
    "current_time_statement", "current_meal_statement",
    "page_context", "raw_page_context", "tool_context",
    "dashboard_summary", "user_settings", "recent_records",
    "personalized_food_decision", "recommendation_level",
    "consumed_calories", "target_calories", "remaining_calories", "record_count",
    "food_context_risks", "recommendation_basis",
    "status", "status_label",
    "decision", "food_estimate",
    "time_context", "food_context_risks",
    "estimated_after_eating", "remaining_after_eating",
    "recent_high_fat_count", "recent_similar_food_count",
    "today_fat_consumed", "target_fat",
    "estimated_calories", "estimated_min", "estimated_max", "estimated_fat",
    "goal_type", "nutrition_goal_mode",
    "response_style", "max_words",
    "today", "weekly_statistics", "food_record",
    "reasoning_result", "request_type", "decision_mode", "required_tools",
    "local_minute", "local_time_text",
}

FORBIDDEN_OUTPUT_TERMS = {
    "local_hour", "client_time_iso", "timezone",
    "meal_period", "has_known_local_time",
    "current_time_statement", "current_meal_statement",
    "page_context", "tool_context",
    "dashboard_summary", "user_settings", "recent_records",
    "personalized_food_decision", "recommendation_level",
    "consumed_calories", "target_calories", "remaining_calories",
    "record_count", "food_context_risks", "recommendation_basis",
    "response_style", "max_words", "food_estimate",
    "decision", "today_fat_consumed",
    "estimated_after_eating", "remaining_after_eating",
    "recent_high_fat_count", "recent_similar_food_count",
    "reasoning_result", "request_type", "decision_mode", "required_tools",
    "local_minute", "local_time_text", "out_of_scope",
}

SYSTEM_PROMPT = """你是 FoodFlow 的产品内 AI 饮食助手，回答要简洁、清楚、可操作。

回答风格规则（严格遵守）：
- 先说一句直接结论，再用 2-3 个短点解释原因，最后给 1 个下一步建议。
- 每条回答控制在 80-180 字，不要写长段落。
- 不要写 markdown 表格。
- 不要输出任何英文字段名、数据库字段名、内部变量名或 JSON。
- 用词规则：
  - "confirmed" → "已保存记录"
  - "draft / pending / processing" → "未保存 / 待确认 / 处理中"
  - 热量目标 → "每日热量目标"
- 用户问统计时，只提最关键的数字，不要把所有营养字段都列出来。
- 用户问"为什么没有记录"时，优先解释原因，不要堆数据。
- 如果有处理中的记录，可以提醒"有一条正在处理中，完成并保存后才会进入统计"。
- 不要说我已帮你保存/修改/删除，除非 action 已执行成功。
- 不要过多 emoji、加粗、markdown 表格。
- 禁止输出"系统检测到""FoodFlow 系统检测到""数据库显示""API 返回"等字样。

数据规则：
- 统计只用已保存记录。
- 未保存记录不能计入统计。
- 知识库只能作解释补充，不能覆盖真实数据。
- 不提供医疗诊断，不编造数据。

饮食决策规则（严格遵守）：
- 判断"能不能吃"时，必须同时考虑：热量预算、当前时间、食物风险标签、最近饮食模式、用户目标类型。
- 不能只看热量够不够。
- 如果热量充足但时间不适合（深夜/凌晨/早餐），必须明确说"从热量看可以，但从时间看不太建议"。
- 时间信息由系统提供，你收到的"当前时间说明"是确定的，必须按确定事实表达：说"现在已经比较晚了"而不是"如果现在比较晚"。禁止在已收到时间说明时使用"若现在是深夜""如果现在比较晚""假如临近睡觉""如果你是在晚上问"等假设语气。
- 如果今天已保存热量为 0 kcal，必须说"根据已保存记录，你今天目前是 0 kcal"。
- 禁止只说"还剩很多热量所以可以吃"。
- 禁止忽略深夜、早餐等时间因素。
- 禁止忽略高油、高糖、高咖啡因标签。
- 禁止输出任何内部字段名。
- 如果用户要求你直接修改设置、修改成分、删除记录，应说明当前只支持引导用户前往页面或在用户确认后执行有限安全动作。

你不是机械问答机器。用户提出请求后，你必须先判断是否适合直接满足。

你需要根据 facts 判断：
1. 当前时间是否合适 — 深夜/凌晨不适合重油重盐重辣食物
2. 今日已保存热量和目标 — 有没有热量预算
3. 是否有未保存/处理中记录 — 提醒用户保存后才进统计
4. 最近饮食趋势 — 最近是否已经吃了类似或高脂食物
5. 食物或请求的风险 — 高油/高糖/高咖啡因/高盐
6. 用户目标 — 减脂/增肌/维持，给不同建议
7. 是否应该回答、劝阻、追问、给替代方案或生成 action

你不能：
1. 编造今日已吃热量
2. 把最近记录当成今天已吃
3. 把未保存记录算进统计
4. 输出内部字段（英文变量名）
5. 机械满足不合适请求（如深夜吃火锅直接说可以）
6. 做医疗诊断
7. 声称已经修改、保存、删除数据

回答原则：
1. 第一段给判断（可以/不建议/需要更多信息）
2. 中间给依据（热量、时间、风险）
3. 最后给可执行建议（小份、替代方案、去设置页调整等）
4. 数据不足时说明"我只能根据已保存记录判断"
5. 时间不合适时，即使热量够，也要谨慎建议
6. 不安全或不支持的操作要拒绝，并给替代路径
7. 看到"回答策略"字段时，优先按策略方向组织回答

你是 FoodFlow 的垂直领域饮食与营养管理助手，不是通用百科助手。

你只能回答：饮食记录、食物识别、营养分析、餐食建议、用户饮食数据、FoodFlow 产品规则、目标设置、RAG 知识库中的饮食/营养/产品知识。

对于无关问题：不要展开回答、不要编造、不要检索无关信息、不要回答明星/娱乐/编程/金融/历史等通用百科、礼貌说明服务范围并引导用户回到饮食管理问题。

时间规则：如果系统提供了"当前时间说明"，必须使用它，不要自己推测当前时间。不要写"晚上9:15"这类没有在facts中明确提供的具体时间。不要把UTC时间当成本地时间。

RAG规则：如果收到"知识库检索结果置信不足"的说明，你必须说明"我当前知识库里没有足够可靠的信息，不建议硬猜"，不要编造知识。"""


# ═══════════════════════════════════════════════════════════════
# Global context sanitizer — all LLM inputs go through this
# ═══════════════════════════════════════════════════════════════

def sanitize_llm_context(tool_context: dict, page_context: dict | None = None) -> dict:
    """Convert raw tool_context into Chinese-only, LLM-safe facts dict.
    ALL LLM calls must use this — not raw tool_context, not _sanitize_tool_context.
    """
    if not tool_context:
        return {}

    result: dict = {}

    # ── food_decision path: already handled by build_food_decision_facts_for_llm ──
    if "food_decision_facts" in tool_context:
        logger.warning("TRACE_LLM_CONTEXT_SANITIZED_KEYS keys=%s", list(tool_context.keys()))
        return tool_context

    # ── personalized_food_decision: use specialized builder ──
    if "personalized_food_decision" in tool_context:
        facts = build_food_decision_facts_for_llm(tool_context)
        logger.warning("TRACE_LLM_CONTEXT_SANITIZED_KEYS keys=%s", list(facts.keys()))
        return {"food_decision_facts": facts}

    # ── meal_plan_advice ──
    if "meal_plan_advice" in tool_context:
        mp = tool_context["meal_plan_advice"]
        facts = _build_meal_plan_facts(mp)
        logger.warning("TRACE_LLM_CONTEXT_SANITIZED_KEYS keys=%s", list(facts.keys()))
        return {"meal_plan_facts": facts}

    # ── dashboard_summary → Chinese ──
    if "dashboard_summary" in tool_context:
        dash = tool_context["dashboard_summary"]
        result["今日汇总"] = {
            "已保存热量": f"{dash.get('consumed_calories', 0)} kcal",
            "热量目标": f"{dash.get('target_calories', 2000)} kcal",
            "剩余热量": f"{dash.get('remaining_calories', 0)} kcal",
            "蛋白质": f"{dash.get('protein', 0)}g",
            "碳水": f"{dash.get('carbs', 0)}g",
            "脂肪": f"{dash.get('fat', 0)}g",
        }
        if dash.get("record_count", 0) == 0:
            result["今日汇总"]["提示"] = "今天还没有已保存记录。如果有正在处理或未保存的餐图，完成确认保存后才会进入统计。"

    # ── user_settings → Chinese ──
    if "user_settings" in tool_context:
        s = tool_context["user_settings"]
        goal_labels = {"maintain": "维持体重", "lose": "减脂", "gain": "增肌"}
        result["营养目标"] = {
            "每日热量目标": f"{s.get('target_calories', 2000)} kcal",
            "蛋白质目标": f"{s.get('target_protein') or '未设置'}g",
            "碳水目标": f"{s.get('target_carbs') or '未设置'}g",
            "脂肪目标": f"{s.get('target_fat') or '未设置'}g",
            "目标类型": goal_labels.get(s.get("goal_type", ""), "维持体重"),
        }

    # ── recent_records → Chinese ──
    if "recent_records" in tool_context:
        recent = tool_context["recent_records"]
        if recent:
            items = []
            for r in recent[:5]:
                items.append(f"{r.get('name', '')} {r.get('calories', 0)}kcal")
            result["最近饮食"] = items

    # ── weekly_statistics → Chinese ──
    if "weekly_statistics" in tool_context:
        w = tool_context["weekly_statistics"]
        result["本周统计"] = {
            "周期": f"{w.get('week_start', '')} 至 {w.get('week_end', '')}",
            "记录数": f"{w.get('record_count', 0)} 条",
            "日均热量": f"{w.get('avg_daily_calories', 0)} kcal",
            "总热量": f"{w.get('total_calories', 0)} kcal",
            "蛋白质合计": f"{w.get('total_protein', 0)}g",
            "碳水合计": f"{w.get('total_carbs', 0)}g",
            "脂肪合计": f"{w.get('total_fat', 0)}g",
        }

    # ── daily_snapshot → Chinese (daily_history path) ──
    if "daily_snapshot" in tool_context:
        ds = tool_context["daily_snapshot"]
        daily_facts = {
            "日期": ds.get("date", ""),
            "日期标签": ds.get("date_label", ""),
            "已保存记录数": ds.get("record_count", 0),
            "总热量": f"{ds.get('total_calories', 0)} kcal",
            "蛋白质": f"{ds.get('protein', 0)}g",
            "碳水": f"{ds.get('carbs', 0)}g",
            "脂肪": f"{ds.get('fat', 0)}g",
        }
        records = ds.get("records", [])
        if records:
            daily_facts["记录摘要"] = [
                f"{r.get('name', '')} {r.get('calories', 0)}kcal"
                for r in records[:10]
            ]
        if ds.get("record_count", 0) == 0:
            daily_facts["提示"] = "该日期没有已保存记录，摄入为 0 kcal。"
        result["历史单日饮食统计"] = daily_facts
        logger.warning("TRACE_DAILY_FACTS_BUILT record_count=%s total_calories=%s",
                       ds.get("record_count", 0), ds.get("total_calories", 0))

    # ── food_record → Chinese ──
    if "food_record" in tool_context:
        fr = tool_context["food_record"]
        result["当前记录"] = {
            "名称": fr.get("name", ""),
            "重量": fr.get("weight", ""),
            "热量": f"{fr.get('calories', 0)} kcal",
            "蛋白质": f"{fr.get('protein', 0)}g",
            "碳水": f"{fr.get('carbs', 0)}g",
            "脂肪": f"{fr.get('fat', 0)}g",
            "状态": "已保存" if fr.get("is_confirmed") else "未保存（不会进入统计）",
        }

    # ── rag_results → pass through (already safe) ──
    if "rag_results" in tool_context:
        result["知识库"] = tool_context["rag_results"]

    # Phase 16: Attach cleaned memory summary
    memory_facts = _build_memory_facts_summary(tool_context)
    if memory_facts:
        result["用户偏好与饮食模式"] = memory_facts

    # ── Safety: strip any remaining forbidden keys ──
    result = _strip_forbidden_keys(result)

    logger.warning("TRACE_LLM_CONTEXT_SANITIZED_KEYS keys=%s", list(result.keys()))
    return result


def _strip_forbidden_keys(obj: any) -> any:
    """Recursively remove forbidden keys from any dict."""
    if isinstance(obj, dict):
        return {
            k: _strip_forbidden_keys(v)
            for k, v in obj.items()
            if k not in FORBIDDEN_LLM_INPUT_KEYS
        }
    if isinstance(obj, list):
        return [_strip_forbidden_keys(item) for item in obj]
    return obj


# ═══════════════════════════════════════════════════════════════
# Meal plan facts builder
# ═══════════════════════════════════════════════════════════════

MEAL_PLAN_OPTIONS = {
    "late_night": ["无糖酸奶", "水煮蛋", "少量水果", "热牛奶", "小份燕麦", "黄瓜", "小番茄"],
    "breakfast": ["全麦面包+鸡蛋", "无糖豆浆+燕麦", "蒸红薯+牛奶", "水煮蛋+水果"],
    "lunch": ["清蒸鱼+蔬菜", "鸡胸肉沙拉", "糙米饭+瘦肉", "豆腐蔬菜汤"],
    "afternoon": ["坚果一小把", "无糖酸奶", "水果", "全麦饼干"],
    "dinner": ["清蒸鱼+蔬菜", "瘦肉+杂粮饭", "豆腐+绿叶菜", "少油炒菜+小碗米饭"],
    "general": ["清蒸/水煮做法", "多蔬菜", "少油少盐", "小份优先"],
}


def _build_meal_plan_facts(mp: dict) -> dict:
    """Build Chinese-only facts for meal plan advice."""
    facts: dict = {
        "任务": mp.get("task", "给用户制定饮食建议"),
    }

    tc = mp.get("time_context", {})
    if isinstance(tc, dict):
        if tc.get("current_time_statement"):
            facts["当前时间说明"] = tc["current_time_statement"]
        if tc.get("current_meal_statement"):
            facts["餐次建议"] = tc["current_meal_statement"]

    dc = mp.get("decision", {})
    if isinstance(dc, dict):
        consumed = dc.get("consumed_calories", 0)
        target = dc.get("target_calories", 2000)
        remaining = dc.get("remaining_calories", target)
        facts["今日已保存热量"] = f"{consumed} kcal"
        facts["今日热量目标"] = f"{target} kcal"
        facts["今日剩余热量"] = f"{remaining} kcal"
        if dc.get("record_count", 0) == 0:
            facts["统计说明"] = "今天还没有已保存记录，未保存或正在处理的餐图不会计入。如果系统有处理中的任务，请提醒用户完成确认并保存。"

    period = mp.get("meal_period", "general")
    options = MEAL_PLAN_OPTIONS.get(period, MEAL_PLAN_OPTIONS["general"])
    facts["可选方案"] = options

    recent = mp.get("recent_records", [])
    if recent:
        names = [f"{r.get('name','')} {r.get('calories',0)}kcal" for r in recent[:3]]
        facts["最近饮食"] = names

    return _strip_forbidden_keys(facts)


# ═══════════════════════════════════════════════════════════════
# Memory facts helper (Phase 16)
# ═══════════════════════════════════════════════════════════════

def _build_memory_facts_summary(tool_context: dict) -> list[str]:
    """Extract cleaned memory summary from tool_context memory_context.

    Returns user-visible Chinese text only. Never raw value_json, ids, or timestamps.
    avoid_foods / allergens only trigger strong reminders when the current food/entity matches.
    """
    mem = tool_context.get("memory_context") or tool_context.get("personalized_food_decision", {}).get("memory_context")
    if not mem or not isinstance(mem, dict):
        return []

    # Determine current food/entity name for contextual matching
    current_food = ""
    pfd = tool_context.get("personalized_food_decision", {})
    if isinstance(pfd, dict):
        current_food = pfd.get("food_name", "") or ""

    lines: list[str] = []

    # Explicit preferences
    explicit = mem.get("explicit_preferences", {})
    if isinstance(explicit, dict):
        avoid = explicit.get("avoid_foods", [])
        if avoid and isinstance(avoid, list) and len(avoid) > 0:
            hit = any(a for a in avoid if a and current_food and a in current_food)
            if hit:
                # Strong reminder: current food/drink matches avoid list
                hit_items = [a for a in avoid if a and current_food and a in current_food]
                food_list = "、".join(str(f) for f in hit_items[:3])
                lines.append(f"用户设置里把{food_list}列为避开食物/饮品，建议不选它")
            else:
                # Weak context: avoid list exists but not relevant to current query
                food_list = "、".join(str(f) for f in avoid[:5])
                lines.append(f"用户设置中有避开食物/饮品列表：{food_list}。仅在讨论这些食物时才提醒。")

        allergens = explicit.get("allergens", [])
        if allergens and isinstance(allergens, list) and len(allergens) > 0:
            hit = any(a for a in allergens if a and current_food and a in current_food)
            if hit:
                # Only warn when current food matches allergen list
                lines.append("用户设置里有与当前食物相关的过敏信息，建议避免或先确认")
            # No hit → no allergen warning at all (don't spam generic warnings)

    # Inferred patterns
    inferred = mem.get("inferred_patterns", [])
    if isinstance(inferred, list):
        for p in inferred:
            if not isinstance(p, dict):
                continue
            if p.get("key") == "spicy_hotpot_like_frequency" and p.get("level") == "high":
                lines.append("最近已保存记录中麻辣烫/冒菜/火锅/烧烤类偏多，建议这次注意控制油和份量")
            elif p.get("key") == "recent_high_fat_pattern" and p.get("level") == "high":
                lines.append("最近已保存记录中高油餐出现较多，建议这次选清淡做法")
            elif p.get("key") == "frequent_sugary_drink_pattern":
                lines.append("最近含糖饮品出现得比较多，建议这次优先选无糖替代")

    return lines


# ═══════════════════════════════════════════════════════════════
# Food decision facts (existing, kept intact)
# ═══════════════════════════════════════════════════════════════

def build_food_decision_facts_for_llm(decision_context: dict) -> dict:
    """Build a Chinese-only, user-facing facts dict for LLM.
    No internal field names (local_hour, consumed_calories, etc.) allowed.
    """
    d = decision_context.get("personalized_food_decision", {}) or decision_context
    dc = d.get("decision", {})
    tc = dc.get("time_context", {})
    est = d.get("food_estimate", {})
    food_name = d.get("food_name", "")

    facts = {
        "任务": "根据用户今天的饮食状态，判断现在是否适合吃这个食物。",
    }

    if tc.get("current_time_statement"):
        facts["当前时间说明"] = tc["current_time_statement"]
    if tc.get("current_meal_statement"):
        facts["餐次建议"] = tc["current_meal_statement"]

    consumed = dc.get("consumed_calories", 0)
    target = dc.get("target_calories", 2000)
    remaining = dc.get("remaining_calories", target)
    record_count = dc.get("record_count", 0)

    facts["今日已保存热量"] = f"{consumed} kcal"
    facts["今日热量目标"] = f"{target} kcal"
    facts["今日剩余热量"] = f"{remaining} kcal"

    if record_count == 0:
        facts["统计说明"] = "这里只根据已保存记录判断，未保存或正在处理的餐图暂时不会计入。如果系统有处理中的任务，请提醒用户完成确认并保存。"
    else:
        facts["统计说明"] = "以上基于已保存记录统计。"

    if food_name:
        facts["食物名称"] = food_name
    if est.get("typical"):
        facts["食物热量估算"] = f"普通一份大约 {est.get('min', '?')}–{est.get('max', '?')} kcal"

    risk_tags = est.get("risk_tags", [])
    if risk_tags:
        facts["食物特点"] = risk_tags

    better = est.get("better_choices", [])
    if better:
        facts["推荐选择"] = better[:4]
    avoid = est.get("avoid_choices", [])
    if avoid:
        facts["建议少选"] = avoid[:4]

    recent = d.get("recent_records", [])
    if recent:
        facts["最近饮食提示"] = "最近已保存记录只用于判断饮食趋势，不计入今天已吃。以下是最近几顿："
        recent_names = [f"{r.get('name','')} {r.get('calories',0)}kcal" for r in recent[:3]]
        facts["最近几顿"] = recent_names

    # Phase 16: Attach cleaned memory summary (from memory_context in tool_context)
    # Only passes user-visible summary text, never raw value_json, ids, or timestamps
    memory_facts = _build_memory_facts_summary(decision_context)
    if memory_facts:
        facts["用户偏好与饮食模式"] = memory_facts

    return _strip_forbidden_keys(facts)


# ═══════════════════════════════════════════════════════════════
# Build user content (ALL paths use sanitized context)
# ═══════════════════════════════════════════════════════════════

def _build_user_content(
    user_message: str,
    page: str,
    page_context: dict,
    tool_context: dict,
) -> str:
    """Build LLM user message. ALL tool_context goes through sanitize_llm_context.
    page_context is NEVER passed to LLM directly — only page name is used.
    """
    safe_context = sanitize_llm_context(tool_context, page_context)

    # Verify no forbidden keys leaked
    raw_json = json.dumps(safe_context, ensure_ascii=False)
    leaked = []
    for key in FORBIDDEN_LLM_INPUT_KEYS:
        if f'"{key}"' in raw_json or f"'{key}'" in raw_json:
            leaked.append(key)
    if leaked:
        logger.error("TRACE_LLM_CONTEXT_HAS_FORBIDDEN_FIELDS has_forbidden=true leaked=%s", leaked)
    else:
        logger.warning("TRACE_LLM_CONTEXT_HAS_FORBIDDEN_FIELDS has_forbidden=false")

    parts = []
    if safe_context:
        parts.append("FoodFlow 数据：")
        parts.append(json.dumps(safe_context, ensure_ascii=False, indent=2))
    if page:
        parts.append(f"当前页面：{page}")
    parts.append(f"用户问题：{user_message}")
    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# Global output validation
# ═══════════════════════════════════════════════════════════════

def validate_no_internal_fields(answer: str) -> tuple[bool, list[str]]:
    """Check answer for ANY internal field names. Used on ALL assistant outputs."""
    if not answer:
        return True, []
    issues = []
    answer_lower = answer.lower()
    for term in FORBIDDEN_OUTPUT_TERMS:
        if term.lower() in answer_lower:
            issues.append(f"internal_field:{term}")
    # Also check for "系统检测到" / "FoodFlow 系统" patterns
    system_leak_patterns = [
        r"系统检测到",
        r"FoodFlow\s*系统",
        r"数据库.*显示",
        r"API\s*返回",
    ]
    for p in system_leak_patterns:
        if re.search(p, answer):
            issues.append(f"system_leak:{p}")
    return len(issues) == 0, issues


def validate_food_decision_answer(answer: str, facts: dict) -> tuple[bool, list[str]]:
    """Validate that the answer doesn't contain internal fields or fabricated numbers."""
    issues = []

    # 1. Internal field names
    ok, field_issues = validate_no_internal_fields(answer)
    if not ok:
        issues.extend(field_issues)

    # 2. Number consistency
    saved_str = facts.get("今日已保存热量", "0 kcal")
    saved_match = re.search(r"(\d+)", str(saved_str))
    saved_num = int(saved_match.group(1)) if saved_match else 0

    consumed_patterns = [
        r"(?:你)?今日已摄入\s*(\d+)\s*kcal",
        r"(?:你)?今天已吃\s*(\d+)\s*kcal",
        r"(?:你)?已摄入\s*(\d+)\s*kcal",
        r"(?:你)?已吃\s*(\d+)\s*kcal",
        r"(?:你)?今天已摄入\s*(\d+)\s*千卡",
        r"(?:你)?已摄入了?\s*(\d+)\s*kcal",
        r"今日摄入[约]?\s*(\d+)\s*kcal",
        r"你今天摄入了\s*(\d+)\s*kcal",
    ]
    for p in consumed_patterns:
        m = re.search(p, answer)
        if m and int(m.group(1)) != saved_num:
            issues.append(f"wrong_consumed:{m.group(1)}!={saved_num}")
            break

    target_str = facts.get("今日热量目标", "")
    target_match = re.search(r"(\d+)", str(target_str))
    target_num = int(target_match.group(1)) if target_match else 2000
    target_patterns = [
        r"(?:每日)?目标(?:热量)?[约]?\s*(\d+)\s*kcal",
        r"日[标標]\s*(\d+)\s*kcal",
        r"目标[约]?\s*(\d+)\s*(?:千卡|kcal)",
    ]
    for p in target_patterns:
        m = re.search(p, answer)
        if m and int(m.group(1)) != target_num:
            issues.append(f"wrong_target:{m.group(1)}!={target_num}")
            break

    # 3. Hypothetical language when time is known
    if facts.get("当前时间说明"):
        hypotheticals = ["若当前", "如果当前", "若现在", "如果现在", "若是深夜", "如果是早上", "如果是中午"]
        for h in hypotheticals:
            if h in answer:
                issues.append(f"hypothetical_time:{h}")

    return len(issues) == 0, issues


def validate_assistant_answer(
    answer: str,
    facts: dict | None = None,
    reasoning: AssistantReasoningResult | None = None,
) -> tuple[bool, list[str]]:
    """Enhanced validation for ALL request types. Number consistency + internal fields + refusal check."""
    issues: list[str] = []

    # 1. Internal field check (always)
    ok, field_issues = validate_no_internal_fields(answer)
    if not ok:
        issues.extend(field_issues)

    # 2. Forbidden action: must NOT claim execution
    if reasoning and reasoning.request_type == "forbidden_action":
        forbidden_claims = ["已帮你", "已为你", "已经保存", "已经删除", "已经修改", "已经清空", "已删除", "已修改"]
        for w in forbidden_claims:
            if w in answer:
                issues.append(f"forbidden_action_claim:{w}")

    # 3. Forbidden action: must contain refusal language (NOT applied to out_of_scope)
    if reasoning and reasoning.request_type == "forbidden_action":
        refusal_indicators = ["不支持", "不可以", "无法", "不能", "抱歉", "手动"]
        if not any(ind in answer for ind in refusal_indicators):
            issues.append("missing_refusal_language")

    # 3b. Daily history: forbid product-limitation lies
    if reasoning and reasoning.request_type == "daily_history":
        forbidden_phrases = [
            "只能查看今日", "只支持今日", "无法查看历史", "无法查看昨日",
            "不能查看昨日", "不支持历史", "请去历史页面", "请去报告页",
            "当前不支持历史记录", "只提供今日", "只能今日",
            "去饮食记录页面", "去页面查看", "到页面去查看", "去记录页",
            "请前往页面", "请到页面",
        ]
        for phrase in forbidden_phrases:
            if phrase in answer:
                issues.append(f"daily_history_forbidden_phrase:{phrase}")

    # 4. Number consistency (for ALL request types with calorie data)
    if facts:
        # Top-level consumed checks
        saved_str = facts.get("今日已保存热量", "")
        if saved_str:
            saved_match = re.search(r"(\d+)", str(saved_str))
            saved_num = int(saved_match.group(1)) if saved_match else None
            if saved_num is not None:
                consumed_patterns = [
                    r"(?:你)?今日已摄入\s*(\d+)\s*kcal",
                    r"(?:你)?今天已吃\s*(\d+)\s*kcal",
                    r"(?:你)?已摄入\s*(\d+)\s*kcal",
                    r"(?:你)?已吃\s*(\d+)\s*kcal",
                    r"(?:你)?今天已摄入\s*(\d+)\s*千卡",
                    r"今日摄入[约]?\s*(\d+)\s*kcal",
                    r"你今天摄入了\s*(\d+)\s*kcal",
                ]
                for p in consumed_patterns:
                    m = re.search(p, answer)
                    if m and int(m.group(1)) != saved_num:
                        issues.append(f"wrong_consumed:{m.group(1)}!={saved_num}")
                        break

        # Top-level target checks
        target_str = facts.get("今日热量目标", "")
        if target_str:
            target_match = re.search(r"(\d+)", str(target_str))
            target_num = int(target_match.group(1)) if target_match else None
            if target_num is not None:
                target_patterns = [
                    r"(?:每日)?目标(?:热量)?[约]?\s*(\d+)\s*kcal",
                    r"日[标標]\s*(\d+)\s*kcal",
                    r"目标[约]?\s*(\d+)\s*(?:千卡|kcal)",
                ]
                for p in target_patterns:
                    m = re.search(p, answer)
                    if m and int(m.group(1)) != target_num:
                        issues.append(f"wrong_target:{m.group(1)}!={target_num}")
                        break

        # Hypothetical time language
        if facts.get("当前时间说明"):
            hypotheticals = ["若当前", "如果当前", "若现在", "如果现在", "若是深夜", "如果是早上", "如果是中午"]
            for h in hypotheticals:
                if h in answer:
                    issues.append(f"hypothetical_time:{h}")

        # 5. Time-period consistency check
        time_statement = facts.get("当前时间说明", "")
        if "早上" in time_statement or "上午" in time_statement or "现在是早上" in time_statement:
            forbidden_terms = ["晚上", "临近晚间", "夜深", "深夜", "睡前", "夜宵", "晚餐", "晚饭"]
            for t in forbidden_terms:
                if t in answer:
                    issues.append(f"time_mismatch:morning_has_evening_term:{t}")
        if "深夜" in time_statement or "比较晚了" in time_statement or "夜宵" in time_statement:
            forbidden_terms = ["早上", "上午", "早餐", "早饭"]
            for t in forbidden_terms:
                if t in answer:
                    issues.append(f"time_mismatch:night_has_morning_term:{t}")

        # 6. Daily history validation (reads Chinese keys from sanitized context)
        daily_snap = facts.get("历史单日饮食统计", {})
        if isinstance(daily_snap, dict):
            daily_count = daily_snap.get("已保存记录数", -1)
            total_cal_str = str(daily_snap.get("总热量", "0 kcal"))
            cal_match = re.search(r"(\d+)", total_cal_str)
            daily_cal = int(cal_match.group(1)) if cal_match else 0

            if daily_count == 0 or daily_cal == 0:
                # Forbid fabricated positive intake when data is empty
                daily_intake_patterns = [
                    r"(?:昨天|前天|上周.{0,3}|那.{0,3}天|目标日期)\s*摄入了?\s*(\d+)\s*kcal",
                    r"(?:昨天|前天|上周.{0,3}|那.{0,3}天|目标日期)\s*摄入\s*(\d+)\s*千卡",
                    r"(?:昨天|前天|上周.{0,3}|那.{0,3}天)\s*吃了\s*(\d+)\s*kcal",
                    r"摄入了\s*(\d+)\s*kcal",
                    r"摄入\s*(\d+)\s*千卡",
                    r"吃了\s*(\d+)\s*kcal",
                ]
                for p in daily_intake_patterns:
                    m = re.search(p, answer)
                    if m and int(m.group(1)) > 0:
                        issues.append(f"daily_zero_calorie_fabrication:{m.group(1)}kcal")
                        break

            elif daily_count > 0 and daily_cal > 0:
                # Forbid "no data" claims when data actually exists
                no_data_phrases = [
                    "暂无已保存数据", "没有该日期记录", "没有已保存记录",
                    "未找到记录", "无法确认是否属于该日期",
                ]
                for phrase in no_data_phrases:
                    if phrase in answer:
                        issues.append(f"daily_has_data_but_claims_none:{phrase}")
                        break

        # Nested facts check (今日汇总, 本周统计, 营养目标, 当前记录, 历史单日饮食统计)
        for top_key in ["今日汇总", "本周统计", "营养目标", "当前记录", "历史单日饮食统计"]:
            nested = facts.get(top_key, {})
            if isinstance(nested, dict):
                nested_saved = nested.get("已保存热量", "")
                if nested_saved:
                    nested_match = re.search(r"(\d+)", str(nested_saved))
                    nested_num = int(nested_match.group(1)) if nested_match else None
                    if nested_num is not None:
                        for p in consumed_patterns:
                            m = re.search(p, answer)
                            if m and int(m.group(1)) != nested_num:
                                issues.append(f"wrong_nested_consumed:{top_key}:{m.group(1)}!={nested_num}")
                                break

    return len(issues) == 0, issues


# ═══════════════════════════════════════════════════════════════
# LLM call helpers
# ═══════════════════════════════════════════════════════════════

def _run_mock(user_message: str, template_fallback: str) -> str:
    logger.info("assistant_llm: mock mode, returning template")
    return template_fallback


def _call_bailian(user_content: str, template_fallback: str) -> str:
    """Call Bailian via OpenAI-compatible API. Falls back to template on any error."""
    if not settings.BAILIAN_API_KEY:
        logger.warning("assistant_llm: BAILIAN_API_KEY not set, fallback to template")
        return template_fallback

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("assistant_llm: openai not installed, fallback to template")
        return template_fallback

    client = OpenAI(
        api_key=settings.BAILIAN_API_KEY,
        base_url=settings.BAILIAN_BASE_URL,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    t0 = time.time()
    logger.warning("TRACE_LLM_CALL_START model=%s", settings.BAILIAN_MODEL)
    try:
        response = client.chat.completions.create(
            model=settings.BAILIAN_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=600,
            timeout=settings.AI_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        elapsed = time.time() - t0

        if not content or not content.strip():
            logger.warning("assistant_llm: empty response, fallback to template (%.1fs)", elapsed)
            return template_fallback

        logger.info("assistant_llm: bailian model=%s latency=%.1fs len=%d",
                    settings.BAILIAN_MODEL, elapsed, len(content))
        logger.warning("TRACE_LLM_CALL_END success=True latency=%.1fs len=%d", elapsed, len(content))
        return content.strip()

    except Exception as e:
        elapsed = time.time() - t0
        logger.warning("assistant_llm: bailian call failed after %.1fs: %s", elapsed, e)
        logger.warning("TRACE_LLM_CALL_END success=False latency=%.1fs error=%s", elapsed, e)
        return template_fallback


# ═══════════════════════════════════════════════════════════════
# Output cleaning
# ═══════════════════════════════════════════════════════════════

def clean_assistant_answer(answer: str) -> str:
    """Post-process LLM answer — strip internal fields, clean formatting."""
    if not answer:
        return answer

    # Strip entire lines containing internal field names
    internal_terms = list(FORBIDDEN_OUTPUT_TERMS) + [
        "estimated_after_eating", "remaining_after_eating",
        "recent_high_fat_count", "recent_similar_food_count",
        "response_style", "max_words",
        "decision", "today_fat_consumed",
        "weekly_statistics", "food_record",
        "系统检测到", "FoodFlow 系统",
    ]
    lines = answer.split("\n")
    filtered = []
    for line in lines:
        stripped = line.strip().lower()
        if any(term in stripped for term in internal_terms):
            logger.warning("clean_assistant_answer: stripped line with internal term: %s", line[:80])
            continue
        filtered.append(line)
    answer = "\n".join(filtered)

    # Replace internal English status terms with Chinese equivalents (word-boundary only)
    answer = re.sub(r'\bconfirmed\b(?![一-鿿])', '已保存', answer)
    answer = re.sub(r'\bdraft\b(?![一-鿿])', '未保存', answer)
    answer = re.sub(r'\bpending\b(?![一-鿿])', '处理中', answer)
    # Strip lines containing raw status/internal/JSON words
    raw_terms = {"status", "internal", "JSON", "json"}
    lines = answer.split("\n")
    filtered = []
    for line in lines:
        stripped = line.strip().lower()
        if any(term.lower() in stripped for term in raw_terms):
            logger.warning("clean_assistant_answer: stripped line with raw term: %s", line[:80])
            continue
        filtered.append(line)
    answer = "\n".join(filtered)

    # Strip JSON code blocks
    answer = re.sub(r"```json[\s\S]*?```", "", answer)
    answer = re.sub(r"```[\s\S]*?```", "", answer)

    # Collapse multiple blank lines
    answer = re.sub(r"\n{3,}", "\n\n", answer)
    answer = answer.strip()

    # Truncate if too long
    if len(answer) > 500:
        answer = answer[:480] + "…\n\n我可以继续展开说明。"

    return answer


# ═══════════════════════════════════════════════════════════════
# Main generation entry points
# ═══════════════════════════════════════════════════════════════

def _generate_and_validate(
    user_content: str,
    template_fallback: str,
    facts: dict | None = None,
    log_prefix: str = "NORMAL",
    reasoning: AssistantReasoningResult | None = None,
) -> str:
    """Core: call LLM, validate output, retry once, fallback on failure."""
    # Forbidden / out_of_scope: skip LLM entirely, return respective template
    if reasoning and reasoning.request_type == "out_of_scope":
        logger.warning("TRACE_DOMAIN_BOUNDARY_SKIP_LLM request_type=%s", reasoning.request_type)
        return clean_assistant_answer(template_fallback)
    if reasoning and reasoning.request_type == "forbidden_action":
        logger.warning("TRACE_REFUSE_UNSAFE_SKIP_LLM request_type=%s", reasoning.request_type)
        return clean_assistant_answer(template_fallback)

    if settings.AI_MODE == "bailian":
        raw = _call_bailian(user_content, template_fallback)
    else:
        raw = _run_mock("", template_fallback)

    logger.warning("TRACE_%s_LLM_RAW_ANSWER len=%d preview=%s", log_prefix, len(raw), raw[:120])

    # Validate — use unified validator that handles all request types
    ok, issues = validate_assistant_answer(raw, facts, reasoning)

    logger.warning("TRACE_%s_VALIDATE_RESULT ok=%s issues=%s", log_prefix, ok, issues)

    if not ok:
        logger.warning("assistant_llm: %s retry, issues=%s", log_prefix, issues)
        retry_prompt = user_content + (
            f"\n\n注意：上次回答出现以下问题：{'；'.join(issues)}。"
            "请修正后重新回答。只输出修正后的回答文本，不要输出任何英文字段名或内部变量名。"
            "不要输出'系统检测到''数据库显示'等字样。"
        )
        if settings.AI_MODE == "bailian":
            raw = _call_bailian(retry_prompt, template_fallback)
        else:
            raw = _run_mock("", template_fallback)

        ok2, issues2 = validate_assistant_answer(raw, facts, reasoning)

        if not ok2:
            logger.error("assistant_llm: %s retry also failed, fallback. issues=%s", log_prefix, issues2)
            return clean_assistant_answer(template_fallback)

    final = clean_assistant_answer(raw)
    logger.warning("TRACE_%s_FINAL_ANSWER len=%d preview=%s", log_prefix, len(final), final[:120])
    return final


def generate_assistant_answer(
    user_message: str,
    page: str,
    page_context: dict,
    tool_context: dict,
    sources: list,
    template_fallback: str,
    reasoning: AssistantReasoningResult | None = None,
) -> str:
    """Generate a natural-language assistant reply. ALL paths sanitized, ALL outputs validated."""

    # Out of scope / forbidden: skip LLM, return respective template
    if reasoning and reasoning.request_type == "out_of_scope":
        logger.warning("TRACE_DOMAIN_BOUNDARY_SKIP_LLM request_type=%s", reasoning.request_type)
        return clean_assistant_answer(template_fallback)
    if reasoning and reasoning.request_type == "forbidden_action":
        logger.warning("TRACE_REFUSE_UNSAFE_SKIP_LLM request_type=%s", reasoning.request_type)
        return clean_assistant_answer(template_fallback)

    # Food decisions: specialized facts + validation
    if reasoning and reasoning.request_type == "food_decision":
        facts = build_food_decision_facts_for_llm(tool_context)
        logger.warning("FOOD_DECISION_FACTS_FOR_LLM consumed=%s target=%s remaining=%s",
                       facts.get('今日已保存热量'), facts.get('今日热量目标'), facts.get('今日剩余热量'))
        user_content = _build_user_content(user_message, page, page_context, {"food_decision_facts": facts})
        return _generate_and_validate(user_content, template_fallback, facts, log_prefix="FOOD_DECISION", reasoning=reasoning)

    # Fallback: also check tool_context keys for backward compat
    if not reasoning and "personalized_food_decision" in tool_context:
        facts = build_food_decision_facts_for_llm(tool_context)
        logger.warning("FOOD_DECISION_FACTS_FOR_LLM consumed=%s target=%s remaining=%s",
                       facts.get('今日已保存热量'), facts.get('今日热量目标'), facts.get('今日剩余热量'))
        user_content = _build_user_content(user_message, page, page_context, {"food_decision_facts": facts})
        return _generate_and_validate(user_content, template_fallback, facts, log_prefix="FOOD_DECISION")

    # Meal plan advice: specialized facts + validation
    if reasoning and reasoning.request_type == "meal_plan":
        mp = tool_context.get("meal_plan_advice", {})
        facts = _build_meal_plan_facts(mp)
        logger.warning("MEAL_PLAN_FACTS_FOR_LLM consumed=%s target=%s",
                       facts.get('今日已保存热量'), facts.get('今日热量目标'))
        user_content = _build_user_content(user_message, page, page_context, {"meal_plan_facts": facts})
        return _generate_and_validate(user_content, template_fallback, facts, log_prefix="MEAL_PLAN", reasoning=reasoning)

    # Fallback: also check tool_context keys
    if not reasoning and "meal_plan_advice" in tool_context:
        mp = tool_context["meal_plan_advice"]
        facts = _build_meal_plan_facts(mp)
        logger.warning("MEAL_PLAN_FACTS_FOR_LLM consumed=%s target=%s",
                       facts.get('今日已保存热量'), facts.get('今日热量目标'))
        user_content = _build_user_content(user_message, page, page_context, {"meal_plan_facts": facts})
        return _generate_and_validate(user_content, template_fallback, facts, log_prefix="MEAL_PLAN")

    # Data-rich paths: use unified facts builder
    if reasoning and reasoning.should_use_user_data and tool_context:
        from app.services.assistant_facts_builder import build_facts_for_llm
        facts = build_facts_for_llm(reasoning, tool_context, page_context)
        logger.warning("TRACE_FACTS_FOR_LLM request_type=%s keys=%s", reasoning.request_type, list(facts.keys()))
        user_content = _build_user_content(user_message, page, page_context, tool_context)
        return _generate_and_validate(user_content, template_fallback, facts=facts if facts else None, log_prefix="DATA", reasoning=reasoning)

    # Normal path: generic sanitized context
    user_content = _build_user_content(user_message, page, page_context, tool_context)
    return _generate_and_validate(user_content, template_fallback, facts=None, log_prefix="NORMAL", reasoning=reasoning)


# ═══════════════════════════════════════════════════════════════
# Streaming helpers
# ═══════════════════════════════════════════════════════════════

def split_text_for_stream(text: str, max_len: int = 60) -> list[str]:
    """Split text into chunks for pseudo-streaming by sentence/segment."""
    if not text:
        return []
    parts = re.split(r"([。！？!?；;\n])", text)
    chunks = []
    current = ""
    for part in parts:
        if not part:
            continue
        current += part
        if part in "。！？!?；;\n" or len(current) >= max_len:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    result = []
    for chunk in chunks:
        if len(chunk) <= max_len:
            result.append(chunk)
        else:
            for i in range(0, len(chunk), max_len):
                result.append(chunk[i : i + max_len])
    return result


async def _stream_bailian(user_content: str, template_fallback: str):
    """Real streaming via AsyncOpenAI. Falls back to pseudo-streaming."""
    if not settings.BAILIAN_API_KEY:
        for chunk in split_text_for_stream(template_fallback):
            yield chunk
        return

    try:
        from openai import AsyncOpenAI
    except ImportError:
        for chunk in split_text_for_stream(template_fallback):
            yield chunk
        return

    client = AsyncOpenAI(
        api_key=settings.BAILIAN_API_KEY,
        base_url=settings.BAILIAN_BASE_URL,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        stream = await client.chat.completions.create(
            model=settings.BAILIAN_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=600,
            stream=True,
            timeout=settings.AI_TIMEOUT_SECONDS,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as e:
        logger.warning("assistant_llm: stream failed: %s, fallback to pseudo-stream", e)
        for chunk in split_text_for_stream(template_fallback):
            yield chunk


async def _stream_mock(user_message: str, template_fallback: str):
    """Mock mode — pseudo-stream template fallback."""
    for chunk in split_text_for_stream(template_fallback):
        yield chunk
        import asyncio
        await asyncio.sleep(0.03)


def _tool_context_has_data(tool_context: dict) -> bool:
    """Check if tool_context contains user-specific data that needs validation."""
    data_keys = {
        "personalized_food_decision", "meal_plan_advice",
        "dashboard_summary", "user_settings", "recent_records",
        "weekly_statistics", "food_record", "daily_snapshot",
    }
    return bool(data_keys & set(tool_context.keys()))


async def generate_assistant_answer_stream(
    user_message: str,
    page: str,
    page_context: dict,
    tool_context: dict,
    sources: list,
    template_fallback: str,
    reasoning: AssistantReasoningResult | None = None,
):
    """Generate a streaming assistant reply.

    Safety rules:
    - Data-rich paths (food_decision, meal_plan, dashboard, etc.):
      generate full → validate → pseudo-stream (no raw tokens ever leave)
    - Refuse/forbidden: pseudo-stream the refusal message
    - No-data paths (greetings, fallback, pure knowledge):
      real streaming OK since no internal fields can leak
    """

    # ── Fast path: Out of scope — pseudo-stream domain boundary ──
    if reasoning and reasoning.request_type == "out_of_scope":
        logger.warning("TRACE_STREAM_MODE mode=domain_boundary path=OUT_OF_SCOPE")
        for chunk in split_text_for_stream(clean_assistant_answer(template_fallback)):
            yield chunk
            import asyncio
            await asyncio.sleep(0.03)
        return

    # ── Fast path: Forbidden action — pseudo-stream refusal ──
    if reasoning and reasoning.request_type == "forbidden_action":
        logger.warning("TRACE_STREAM_MODE mode=refuse_unsafe path=FORBIDDEN_ACTION")
        logger.warning("TRACE_REFUSE_UNSAFE_SKIP_LLM request_type=%s", reasoning.request_type)
        for chunk in split_text_for_stream(clean_assistant_answer(template_fallback)):
            yield chunk
            import asyncio
            await asyncio.sleep(0.03)
        return

    # ── Path A: Food decisions — full gen → validate → pseudo-stream ──
    if (reasoning and reasoning.request_type == "food_decision") or \
       (not reasoning and "personalized_food_decision" in tool_context):
        logger.warning("TRACE_STREAM_MODE mode=validated_pseudo_stream path=FOOD_DECISION")
        facts = build_food_decision_facts_for_llm(tool_context)
        logger.warning("FOOD_DECISION_STREAM_FACTS consumed=%s target=%s remaining=%s",
                       facts.get('今日已保存热量'), facts.get('今日热量目标'), facts.get('今日剩余热量'))
        user_content = _build_user_content(user_message, page, page_context, {"food_decision_facts": facts})
        final_text = _generate_and_validate(user_content, template_fallback, facts, log_prefix="FOOD_DECISION_STREAM", reasoning=reasoning)
        logger.warning("FOOD_DECISION_STREAM_FINAL len=%d preview=%s", len(final_text), final_text[:120])
        for chunk in split_text_for_stream(final_text):
            yield chunk
            import asyncio
            await asyncio.sleep(0.03)
        return

    # ── Path B: Meal plan advice — full gen → validate → pseudo-stream ──
    if (reasoning and reasoning.request_type == "meal_plan") or \
       (not reasoning and "meal_plan_advice" in tool_context):
        logger.warning("TRACE_STREAM_MODE mode=validated_pseudo_stream path=MEAL_PLAN")
        mp = tool_context.get("meal_plan_advice", {})
        facts = _build_meal_plan_facts(mp)
        logger.warning("MEAL_PLAN_STREAM_FACTS consumed=%s target=%s",
                       facts.get('今日已保存热量'), facts.get('今日热量目标'))
        user_content = _build_user_content(user_message, page, page_context, {"meal_plan_facts": facts})
        final_text = _generate_and_validate(user_content, template_fallback, facts, log_prefix="MEAL_PLAN_STREAM", reasoning=reasoning)
        logger.warning("MEAL_PLAN_STREAM_FINAL len=%d preview=%s", len(final_text), final_text[:120])
        for chunk in split_text_for_stream(final_text):
            yield chunk
            import asyncio
            await asyncio.sleep(0.03)
        return

    # ── Path C: Other data-rich paths — full gen → validate → pseudo-stream ──
    has_data = _tool_context_has_data(tool_context) or (reasoning and reasoning.should_use_user_data)
    if has_data:
        logger.warning("TRACE_STREAM_MODE mode=validated_pseudo_stream path=DATA_RICH")
        # Build facts for validation (same as non-streaming path)
        stream_facts = None
        if reasoning and reasoning.should_use_user_data and tool_context:
            from app.services.assistant_facts_builder import build_facts_for_llm
            stream_facts = build_facts_for_llm(reasoning, tool_context, page_context)
        user_content = _build_user_content(user_message, page, page_context, tool_context)
        final_text = _generate_and_validate(user_content, template_fallback, facts=stream_facts, log_prefix="DATA_STREAM", reasoning=reasoning)
        for chunk in split_text_for_stream(final_text):
            yield chunk
            import asyncio
            await asyncio.sleep(0.03)
        return

    # ── Path D: No data — real streaming is safe ──
    logger.warning("TRACE_STREAM_MODE mode=real_streaming path=NO_DATA")
    user_content = _build_user_content(user_message, page, page_context, tool_context)
    if settings.AI_MODE == "bailian":
        async for delta in _stream_bailian(user_content, template_fallback):
            yield delta
    else:
        async for delta in _stream_mock(user_message, template_fallback):
            yield delta
