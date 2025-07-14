"""Phase 18: Action Audit Log service — create, mark success/failed, sanitize.

All audit operations are wrapped in their own try/except.
Audit failure MUST NOT block or rollback the action itself.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_action_log import AssistantActionLog

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 500

# ── Sanitizers ──

def _sanitize_payload(payload: dict | None) -> dict | None:
    """Keep only safe fields: action_type, record_id, page, export_type, report_range."""
    if not payload:
        return None
    allowed = {"action_type", "record_id", "page", "export_type", "report_range"}
    return {k: v for k, v in payload.items() if k in allowed}


def _sanitize_result(result: dict | None) -> dict | None:
    """Keep only summary fields: ok, message, record_id, report_generated,
    observation_available, followup_available, observer_warning."""
    if not result:
        return None
    allowed = {
        "ok", "type", "message", "record_id", "report_generated",
        "observation_available", "followup_available", "observer_warning",
        "opened", "is_saved",
    }
    sanitized = {k: v for k, v in result.items() if k in allowed}
    # Also extract record_id from nested result if not at top level
    if "record_id" not in sanitized and isinstance(result.get("result"), dict):
        rid = result["result"].get("record_id")
        if rid:
            sanitized["record_id"] = rid
    return sanitized


def _sanitize_error(error: Exception | str | None) -> str:
    """Max 500 chars. No traceback. No SQL. No absolute paths. No tokens."""
    if not error:
        return ""
    msg = str(error)
    if len(msg) > MAX_ERROR_LENGTH:
        msg = msg[:MAX_ERROR_LENGTH - 3] + "..."
    # Strip common sensitive patterns
    import re
    msg = re.sub(r'Token\s+\S+', '[REDACTED]', msg)
    msg = re.sub(r'[A-Z]:\\[^\s]{20,}', '[REDACTED_PATH]', msg)
    return msg


# ── Audit log CRUD ──

async def create_action_audit_log(
    db: AsyncSession,
    user_id: str,
    action_id: str | None,
    action_type: str,
    payload: dict | None,
    risk_level: str,
    requires_confirmation: bool,
    before_snapshot: dict | None = None,
) -> AssistantActionLog | None:
    """Create a pending audit log entry before action execution.

    Returns the AssistantActionLog object, or None on failure.
    Caller MUST handle None gracefully (action proceeds without audit).
    """
    try:
        log_entry = AssistantActionLog(
            user_id=user_id,
            action_id=action_id,
            action_type=action_type,
            payload_json=_sanitize_payload(payload),
            status="pending",
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            before_snapshot_json=before_snapshot,
        )
        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)

        logger.warning("TRACE_ACTION_AUDIT_CREATED log_id=%s action_type=%s status=pending",
                       str(log_entry.id), action_type)
        return log_entry
    except Exception as e:
        logger.warning("TRACE_ACTION_AUDIT_FAILED stage=create_pending action_type=%s error=%s",
                       action_type, str(e)[:200])
        try:
            await db.rollback()
        except Exception:
            pass
        return None


async def mark_action_audit_success(
    db: AsyncSession,
    log_id: str,
    result: dict | None = None,
    after_snapshot: dict | None = None,
) -> None:
    """Mark an audit log as success. Swallows errors — must not throw."""
    try:
        stmt = (
            update(AssistantActionLog)
            .where(AssistantActionLog.id == log_id)
            .values(
                status="success",
                result_json=_sanitize_result(result),
                after_snapshot_json=after_snapshot,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await db.execute(stmt)
        await db.commit()
        logger.warning("TRACE_ACTION_AUDIT_MARK_SUCCESS log_id=%s", log_id)
    except Exception as e:
        logger.warning("TRACE_ACTION_AUDIT_FAILED stage=mark_success log_id=%s error=%s",
                       log_id, str(e)[:200])
        try:
            await db.rollback()
        except Exception:
            pass


async def mark_action_audit_failed(
    db: AsyncSession,
    log_id: str,
    error_message: str,
    result: dict | None = None,
) -> None:
    """Mark an audit log as failed. Swallows errors — must not throw."""
    try:
        stmt = (
            update(AssistantActionLog)
            .where(AssistantActionLog.id == log_id)
            .values(
                status="failed",
                error_message=_sanitize_error(error_message),
                result_json=_sanitize_result(result),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await db.execute(stmt)
        await db.commit()
        logger.warning("TRACE_ACTION_AUDIT_MARK_FAILED log_id=%s error_type=%s",
                       log_id, type(error_message).__name__)
    except Exception as e:
        logger.warning("TRACE_ACTION_AUDIT_FAILED stage=mark_failed log_id=%s error=%s",
                       log_id, str(e)[:200])
        try:
            await db.rollback()
        except Exception:
            pass
