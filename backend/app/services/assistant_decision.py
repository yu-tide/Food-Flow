"""Personalized food decision calculator."""
import logging

logger = logging.getLogger(__name__)


def build_meal_time_context(page_context: dict) -> dict:
    """Determine meal period and time-based risks from client local_hour."""
    hour_str = (page_context or {}).get("local_hour", "")
    has_known_time = bool(hour_str)
    try:
        hour = int(hour_str)
    except (ValueError, TypeError):
        hour = 12  # default to noon
        has_known_time = False

    TIME_STATEMENTS = {
        "breakfast":    ("现在是早上。", "现在更适合吃清淡、稳定的早餐。"),
        "lunch":        ("现在接近午餐时间。", "这顿可以按正餐来安排。"),
        "afternoon":    ("现在是下午。", "如果只是加餐，建议控制份量。"),
        "dinner":       ("现在接近晚餐时间。", "这顿可以按晚餐来安排，但要注意别太油。"),
        "late_night":   ("现在已经比较晚了。", "现在更接近夜宵时间，不太适合吃重油重盐的食物。"),
        "midnight":     ("现在已经是深夜了。", "这个时间不太适合吃正常份量的高油高糖食物。"),
    }

    if 5 <= hour < 10:
        period = "breakfast"
        time_risk = "low"
    elif 10 <= hour < 14:
        period = "lunch"
        time_risk = "low"
    elif 14 <= hour < 17:
        period = "afternoon"
        time_risk = "medium"
    elif 17 <= hour < 21:
        period = "dinner"
        time_risk = "low"
    elif 21 <= hour < 24:
        period = "late_night"
        time_risk = "high"
    else:
        period = "midnight"
        time_risk = "high"

    time_stmt, meal_stmt = TIME_STATEMENTS[period]

    logger.warning("TRACE_TIME_CONTEXT has_known=%s meal_period=%s hour=%s statement=%s",
                   has_known_time, period, hour, time_stmt)

    return {
        "local_hour": hour,
        "has_known_local_time": has_known_time,
        "meal_period": period,
        "is_early": period == "breakfast",
        "is_late_night": period in ("late_night", "midnight"),
        "time_risk": time_risk,
        "current_time_statement": time_stmt if has_known_time else "",
        "current_meal_statement": meal_stmt if has_known_time else "",
        "time_advice": meal_stmt if has_known_time else "",
    }


def build_food_decision_context(
    dashboard_summary: dict,
    settings: dict,
    recent_records: list[dict],
    food_estimate: dict,
    page_context: dict | None = None,
) -> dict:
    """Calculate whether a food fits within the user's daily targets.

    CRITICAL: All nutrition figures come ONLY from dashboard_summary (confirmed records).
    recent_records is only used for pattern analysis, never for today's totals.
    """
    # Defensive: force 0 for consumed if no records
    record_count = dashboard_summary.get("record_count", 0)
    consumed = dashboard_summary.get("consumed_calories") or 0
    if record_count == 0:
        consumed = 0

    # Target: dashboard first, then settings, then 2000 fallback
    target = dashboard_summary.get("target_calories") or settings.get("target_calories") or 2000

    # Remaining computed from consumed + target, not from dashboard
    remaining = max(target - consumed, 0)

    today_fat = dashboard_summary.get("fat") or 0
    target_fat = settings.get("target_fat") or 65
    goal_type = settings.get("goal_type", "maintain")

    typical = food_estimate.get("typical") or 0
    min_cal = food_estimate.get("min") or 0
    risk_tags = food_estimate.get("risk_tags", [])

    estimated_after = consumed + typical if typical else consumed
    remaining_after = max(target - estimated_after, 0)

    # Recent patterns only
    recent_high_fat = 0
    for r in recent_records:
        cal = r.get("calories", 0) or 0
        fat = r.get("fat", 0) or 0
        if cal > 0 and fat > cal * 0.35:
            recent_high_fat += 1

    HIGH_RISK_KEYWORDS = ["冒菜", "麻辣烫", "火锅", "烧烤", "炸鸡", "麻辣香锅"]
    recent_similar = sum(1 for r in recent_records
        if any(kw in (r.get("name", "")) for kw in HIGH_RISK_KEYWORDS))

    # ── Multi-factor recommendation ──
    time_ctx = build_meal_time_context(page_context) if page_context else {}
    food_risks = food_estimate.get("context_risks", {}) if isinstance(food_estimate.get("context_risks"), dict) else {}

    level = "yes"
    basis = []

    # Calorie factor
    if typical and remaining < typical:
        if min_cal and remaining >= min_cal:
            level = "small_portion_only"
            basis.append("热量接近上限")
        else:
            level = "not_recommended"
            basis.append("吃完会明显超标")
    elif typical and remaining >= typical + 200:
        if any(tag in risk_tags for tag in ["高油", "高脂", "高钠", "高热量"]):
            level = "yes_but_control"
            basis.append("食物本身偏高油/高热量")
        else:
            basis.append("热量预算充足")
    elif typical and remaining >= typical:
        level = "yes_but_control"
        basis.append("热量勉强够")
    elif not typical:
        level = "yes_but_control"
        basis.append("无法精确估算热量")

    # Time factor
    if time_ctx.get("is_late_night"):
        if level == "yes":
            level = "yes_but_control"
        elif level == "yes_but_control":
            level = "small_portion_only"
        basis.append("当前时间不适合重油/重辣/高糖")

    if time_ctx.get("meal_period") == "breakfast":
        if any(tag in risk_tags for tag in ["高油", "高脂"]):
            if level == "yes":
                level = "yes_but_control"
            basis.append("早餐不太适合高油高脂食物")

    # Food time-specific risks
    if time_ctx.get("meal_period") in food_risks and level != "not_recommended":
        if level == "yes":
            level = "yes_but_control"

    # Fat risk
    if today_fat > 0 and target_fat > 0 and (today_fat + (food_estimate.get("fat") or 0)) > target_fat * 1.1:
        if level == "yes":
            level = "yes_but_control"
        basis.append("脂肪可能超过今日目标")

    # Recent patterns
    if recent_high_fat >= 2 and level == "yes":
        level = "yes_but_control"
        basis.append("最近已有多顿高脂餐")
    if recent_similar >= 2 and level != "not_recommended":
        level = "small_portion_only"
        basis.append("最近已有多顿类似食物")

    decision = {
        "recommendation_level": level,
        "recommendation_basis": basis,
        "consumed_calories": consumed,
        "target_calories": target,
        "remaining_calories": remaining,
        "estimated_calories": typical,
        "estimated_min": min_cal,
        "estimated_max": food_estimate.get("max"),
        "estimated_after_eating": estimated_after,
        "remaining_after_eating": remaining_after,
        "estimated_fat": food_estimate.get("fat"),
        "today_fat_consumed": today_fat,
        "target_fat": target_fat,
        "recent_high_fat_count": recent_high_fat,
        "recent_similar_food_count": recent_similar,
        "goal_type": goal_type,
        "record_count": record_count,
        "time_context": time_ctx,
        "food_context_risks": food_risks,
    }

    logger.debug("assistant_decision: food=%s consumed=%d target=%d remaining=%d after=%d record_count=%d level=%s basis=%s",
        food_estimate.get("food_name", "?"), consumed, target, remaining, remaining_after, record_count, level, basis)

    return decision
