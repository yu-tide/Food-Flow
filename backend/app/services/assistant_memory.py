"""Phase 16: Agent Memory service — user preferences and behavior patterns.

First version: transient inference only on food_decision/meal_plan.
upsert_user_memory() is implemented but not auto-invoked per food_decision.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_memory import AssistantMemory, ALLOWED_MEMORY_TYPES, ALLOWED_SOURCES

logger = logging.getLogger(__name__)


# ── Preference text parser ──

def normalize_preference_text(value: str) -> list[str]:
    """Parse avoid_foods / allergens text into a clean list.

    Supports: Chinese commas, English commas, semicolons, newlines, spaces.
    Example: "奶茶，花生; 香菜、肥肉" → ["奶茶", "花生", "香菜", "肥肉"]
    """
    if not value or not value.strip():
        return []
    parts = re.split(r"[，,;；、\n]+", value)
    return [p.strip() for p in parts if p.strip()]


# ── Read existing memories ──

async def get_user_agent_memories(
    db: AsyncSession,
    user_id: str,
    memory_types: list[str] | None = None,
) -> list[dict]:
    """Read existing memories for a user, optionally filtered by type."""
    try:
        stmt = select(AssistantMemory).where(AssistantMemory.user_id == user_id)
        if memory_types:
            stmt = stmt.where(AssistantMemory.memory_type.in_(memory_types))
        # Exclude expired
        stmt = stmt.where(
            (AssistantMemory.expires_at.is_(None)) |
            (AssistantMemory.expires_at > datetime.now(timezone.utc))
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
        logger.warning("TRACE_ASSISTANT_MEMORY_READ user_id=%s count=%s", user_id[:8], len(rows))
        return [
            {
                "id": str(r.id),
                "memory_type": r.memory_type,
                "key": r.key,
                "value_json": r.value_json or {},
                "confidence": r.confidence,
                "source": r.source,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("TRACE_ASSISTANT_MEMORY_READ_FAILED error=%s", e)
        return []


# ── Upsert (implemented but not auto-invoked) ──

async def upsert_user_memory(
    db: AsyncSession,
    user_id: str,
    memory_type: str,
    key: str,
    value_json: dict,
    confidence: float,
    source: str,
    expires_at: datetime | None = None,
) -> dict | None:
    """Upsert a single memory entry. Not auto-called by food_decision path."""
    if memory_type not in ALLOWED_MEMORY_TYPES:
        logger.warning("TRACE_ASSISTANT_MEMORY_UPSERT_BLOCKED reason=invalid_type type=%s", memory_type)
        return None
    if source not in ALLOWED_SOURCES:
        logger.warning("TRACE_ASSISTANT_MEMORY_UPSERT_BLOCKED reason=invalid_source source=%s", source)
        return None

    try:
        result = await db.execute(
            select(AssistantMemory).where(
                AssistantMemory.user_id == user_id,
                AssistantMemory.memory_type == memory_type,
                AssistantMemory.key == key,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Never overwrite user_explicit with inferred
            if existing.source == "user_explicit" and source == "inferred_from_records":
                logger.warning("TRACE_ASSISTANT_MEMORY_UPSERT_BLOCKED reason=would_overwrite_explicit key=%s", key)
                return None
            existing.value_json = value_json
            existing.confidence = confidence
            existing.source = source
            existing.expires_at = expires_at
            existing.updated_at = datetime.now(timezone.utc)
        else:
            mem = AssistantMemory(
                user_id=user_id, memory_type=memory_type, key=key,
                value_json=value_json, confidence=confidence, source=source,
                expires_at=expires_at,
            )
            db.add(mem)

        await db.commit()
        logger.warning("TRACE_ASSISTANT_MEMORY_UPSERT key=%s confidence=%s source=%s", key, confidence, source)
        return {"ok": True, "key": key, "source": source}
    except Exception as e:
        logger.warning("TRACE_ASSISTANT_MEMORY_UPSERT_FAILED key=%s error=%s", key, e)
        await db.rollback()
        return None


# ── Inference from recent records ──

SPICY_HOTPOT_FOODS = {"冒菜", "麻辣烫", "火锅", "烧烤", "麻辣香锅"}
SUGARY_DRINKS = {"奶茶", "含糖饮料", "可乐", "雪碧", "果汁", "乳饮料", "奶盖", "全糖", "加糖"}


async def infer_memory_from_recent_records(
    db: AsyncSession,
    user_id: str,
    recent_records: list[dict] | None = None,
) -> list[dict]:
    """Analyze recent confirmed records and return transient inferred patterns."""
    if not recent_records:
        return []

    # Confirmed-only whitelist: draft/pending/failed/processing/unconfirmed/None → excluded
    # Compatible with both dict records and ORM objects
    def _is_confirmed(rec) -> bool:
        status = rec.get("status") if isinstance(rec, dict) else getattr(rec, "status", None)
        return status == "confirmed"

    input_count = len(recent_records)
    records = [r for r in recent_records if _is_confirmed(r)]
    logger.warning("TRACE_ASSISTANT_MEMORY_CONFIRMED_FILTER input_count=%s confirmed_count=%s",
                   input_count, len(records))

    if len(records) < 3:
        return []

    patterns: list[dict] = []
    logger.warning("TRACE_ASSISTANT_MEMORY_INFER_START recent_count=%s", len(records))

    # 1. spicy_hotpot_like_frequency
    spicy_count = sum(1 for r in records if any(f in (r.get("name", "") or "") for f in SPICY_HOTPOT_FOODS))
    if spicy_count >= 3:
        patterns.append({
            "key": "spicy_hotpot_like_frequency",
            "level": "high",
            "evidence_count": spicy_count,
            "confidence": 0.75,
            "source": "inferred_from_records",
        })

    # 2. recent_high_fat_pattern
    high_fat_count = 0
    for r in records:
        fat = r.get("fat", 0) or 0
        cal = r.get("calories", 0) or 0
        name = r.get("name", "") or ""
        if fat > 30 and cal > 0 and fat > cal * 0.3:
            high_fat_count += 1
        elif any(f in name for f in {"炸鸡", "烧烤", "火锅", "冒菜", "麻辣烫", "肥牛", "五花肉", "油炸"}):
            high_fat_count += 1
    if high_fat_count >= 3:
        patterns.append({
            "key": "recent_high_fat_pattern",
            "level": "high",
            "evidence_count": high_fat_count,
            "confidence": 0.75,
            "source": "inferred_from_records",
        })

    # 3. frequent_sugary_drink_pattern
    sugary_count = sum(1 for r in records if any(d in (r.get("name", "") or "") for d in SUGARY_DRINKS))
    if sugary_count >= 2:
        patterns.append({
            "key": "frequent_sugary_drink_pattern",
            "level": "moderate" if sugary_count >= 3 else "notable",
            "evidence_count": sugary_count,
            "confidence": 0.70,
            "source": "inferred_from_records",
        })

    # 4. breakfast_missing_pattern — requires meal_type field, skip if not reliable
    # Skipped: meal_type is a free-text String(20), not reliable enough for automated inference
    # No breakfast_missing_pattern returned

    logger.warning("TRACE_ASSISTANT_MEMORY_INFER_RESULT keys=%s", [p["key"] for p in patterns])
    return patterns


# ── Build memory context for food_decision / meal_plan ──

async def build_memory_context_for_food_decision(
    db: AsyncSession,
    user_id: str,
    settings_snapshot: dict | None = None,
    recent_records: list[dict] | None = None,
) -> dict:
    """Build memory_context dict for food_decision / meal_plan branches.

    Combines user_settings explicit preferences + transient inferred patterns.
    Does NOT auto-write to assistant_memories table.
    Gracefully degrades to empty dict on failure.
    """
    try:
        explicit_prefs: dict = {}
        avoid_list: list[str] = []
        allergen_list: list[str] = []

        # Read from settings snapshot
        if settings_snapshot:
            avoid_raw = settings_snapshot.get("avoid_foods", "") or ""
            allergen_raw = settings_snapshot.get("allergens", "") or ""

            avoid_list = normalize_preference_text(avoid_raw)
            allergen_list = normalize_preference_text(allergen_raw)

            explicit_prefs["avoid_foods"] = avoid_list
            explicit_prefs["allergens"] = allergen_list
            explicit_prefs["taste_preference"] = settings_snapshot.get("taste_preference", "normal")
            explicit_prefs["diet_style"] = settings_snapshot.get("diet_style", "normal")
            explicit_prefs["cuisines"] = settings_snapshot.get("cuisines", [])

        logger.warning("TRACE_ASSISTANT_MEMORY_SETTINGS_LOADED avoid_count=%s allergen_count=%s",
                       len(avoid_list), len(allergen_list))

        # Inferred patterns (transient, not persisted)
        inferred = await infer_memory_from_recent_records(db, user_id, recent_records)

        ctx = {
            "explicit_preferences": explicit_prefs,
            "inferred_patterns": inferred,
            "warnings": [],
        }

        logger.warning("TRACE_ASSISTANT_MEMORY_CONTEXT_BUILT explicit_count=%s inferred_count=%s",
                       len(avoid_list) + len(allergen_list) + 3, len(inferred))

        return ctx
    except Exception as e:
        logger.warning("TRACE_ASSISTANT_MEMORY_CONTEXT_FAILED error=%s", e)
        return {}
