"""AI 营养总结服务 — mock / bailian / fallback + Redis cache"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass

from app.core.config import settings
from app.core.redis import get_redis
from app.services.prompt_service import (
    FALLBACK_SUMMARY,
    SYSTEM_MESSAGE,
    build_user_message,
)

logger = logging.getLogger(__name__)

MOCK_SUMMARY = FALLBACK_SUMMARY
CACHE_TTL = 604800  # 7 天
CACHE_PREFIX = "ai_summary"


@dataclass
class AISummaryResult:
    text: str
    engine: str
    latency: str
    success: bool
    fallback_reason: str | None = None


def _write_ai_log(
    *,
    engine: str = "",
    model: str = "",
    prompt_version: str = "",
    prompt_preview: str = "",
    response_preview: str = "",
    latency: str = "",
    token_usage: str = "",
    status: str = "success",
    error_message: str | None = None,
    cache_hit: bool = False,
    user_id: str | None = None,
) -> None:
    """写入 AI 调用日志。写入失败不影响主流程。"""
    try:
        import asyncio
        from app.db.session import async_session
        from app.models.ai_log import AILog as AILogModel

        async def _insert():
            async with async_session() as db:
                db.add(AILogModel(
                    user_id=user_id,
                    engine=engine,
                    model=model,
                    prompt_version=prompt_version,
                    prompt_preview=prompt_preview[:500] if prompt_preview else None,
                    response_preview=response_preview[:500] if response_preview else None,
                    latency=latency,
                    token_usage=token_usage,
                    status=status,
                    error_message=error_message,
                    cache_hit=cache_hit,
                ))
                await db.commit()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_insert())  # fire-and-forget, 不阻塞主任务
        except RuntimeError:
            asyncio.run(_insert())  # 无运行中 event loop，直接同步执行
    except Exception:
        logger.warning("ai_service: log write failed (non-blocking)")


def _build_cache_key(
    food_name: str, total_calories: int, protein: int, carbs: int, fat: int, meal_type: str
) -> str:
    raw = f"{food_name}|{total_calories}|{protein}|{carbs}|{fat}|{meal_type}"
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"{CACHE_PREFIX}:{h}"


def _cache_get(key: str) -> AISummaryResult | None:
    try:
        r = get_redis()
        if r is None:
            return None
        val = r.get(key)
        if val:
            data = json.loads(val)
            return AISummaryResult(**data)
    except Exception as e:
        logger.warning("ai_service: redis get error: %s", e)
    return None


def _cache_set(key: str, result: AISummaryResult) -> None:
    try:
        r = get_redis()
        if r is None:
            return
        data = {
            "text": result.text,
            "engine": result.engine,
            "latency": result.latency,
            "success": result.success,
            "fallback_reason": result.fallback_reason,
        }
        r.setex(key, CACHE_TTL, json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.warning("ai_service: redis set error: %s", e)


def _generate_fallback(
    total_calories: int,
    protein: int,
    carbs: int,
    fat: int,
    reason: str,
) -> AISummaryResult:
    """规则 fallback — 根据营养数据动态生成建议"""
    lines = []
    if protein >= 30:
        lines.append(f"蛋白质摄入 {protein}g，较充足，适合作为正餐。")
    elif protein > 0:
        lines.append(f"蛋白质 {protein}g，可增加鸡蛋、鱼肉或豆制品。")

    if carbs > protein * 1.5 and protein > 0:
        lines.append("碳水占比较高，建议搭配蔬菜或控制主食量。")
    elif carbs > 0:
        lines.append("碳水摄入适中，整体搭配较均衡。")

    if fat <= 15 and fat > 0:
        lines.append("脂肪摄入相对适中，继续保持。")
    elif fat > 15:
        lines.append(f"脂肪 {fat}g，注意减少油炸食品比例。")

    if total_calories <= 600 and total_calories > 0:
        lines.append(f"总热量 {total_calories} kcal，较为适中。")
    elif total_calories > 600:
        lines.append(f"总热量 {total_calories} kcal，偏高，可适当减少分量。")

    if not lines:
        lines = FALLBACK_SUMMARY.split("\n")

    logger.info("ai_service: fallback reason=%s lines=%d", reason, len(lines))
    return AISummaryResult(
        text="\n".join(lines),
        engine="ai-fallback-v1",
        latency="0.0s",
        success=True,
        fallback_reason=reason,
    )


MAX_RETRIES = 2
RETRY_BACKOFF = [0.5, 1.0]


def _call_bailian(messages: list[dict]) -> AISummaryResult:
    """调用阿里云百炼（含轻量 retry）"""
    if not settings.BAILIAN_API_KEY:
        return _generate_fallback(0, 0, 0, 0, "BAILIAN_API_KEY missing")

    try:
        from openai import OpenAI
    except ImportError:
        return _generate_fallback(0, 0, 0, 0, "openai package not installed")

    last_error = ""
    t0 = time.time()
    client = OpenAI(
        api_key=settings.BAILIAN_API_KEY,
        base_url=settings.BAILIAN_BASE_URL,
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=settings.BAILIAN_MODEL,
                messages=messages,
                temperature=0.4,
                timeout=settings.AI_TIMEOUT_SECONDS,
            )
            content = response.choices[0].message.content
            elapsed = time.time() - t0

            token_usage = ""
            try:
                usage = response.usage
                if usage:
                    token_usage = f"p={usage.prompt_tokens},c={usage.completion_tokens},t={usage.total_tokens}"
            except Exception:
                pass

            if not content or not content.strip():
                return _generate_fallback(0, 0, 0, 0, "bailian returned empty content")

            retry_note = f" retries={attempt}" if attempt > 0 else ""
            logger.info("ai_service: bailian model=%s latency=%.1fs len=%d tokens=%s%s",
                        settings.BAILIAN_MODEL, elapsed, len(content), token_usage or "N/A", retry_note)
            _write_ai_log(
                engine="ai-bailian-v1",
                model=settings.BAILIAN_MODEL,
                prompt_version="ai-bailian-v1",
                prompt_preview=messages[-1]["content"][:200] if messages else "",
                response_preview=content[:200],
                latency=f"{elapsed:.1f}s",
                token_usage=token_usage,
                status="success",
            )
            return AISummaryResult(
                text=content.strip(),
                engine="ai-bailian-v1",
                latency=f"{elapsed:.1f}s",
                success=True,
            )
        except Exception as e:
            last_error = str(e)[:200]
            elapsed = time.time() - t0
            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF[attempt]
                logger.warning("ai_service: bailian attempt %d/%d failed after %.1fs: %s, retry in %.1fs",
                              attempt + 1, MAX_RETRIES + 1, elapsed, last_error, backoff)
                time.sleep(backoff)
            else:
                logger.warning("ai_service: bailian all %d attempts failed after %.1fs: %s",
                              MAX_RETRIES + 1, elapsed, last_error)

    elapsed = time.time() - t0
    _write_ai_log(
        engine="ai-bailian-v1",
        model=settings.BAILIAN_MODEL,
        prompt_version="ai-bailian-v1",
        latency=f"{elapsed:.1f}s",
        status="error",
        error_message=f"retries={MAX_RETRIES}: {last_error}",
    )
    return _generate_fallback(0, 0, 0, 0, f"bailian retries exhausted: {last_error}")


def generate_summary(
    *,
    food_name: str = "",
    total_calories: int = 0,
    protein: int = 0,
    carbs: int = 0,
    fat: int = 0,
    meal_type: str = "",
    remark: str = "",
    ocr_text: str = "",
    estimated: bool = False,
) -> AISummaryResult:
    """统一入口"""
    if settings.AI_MODE == "bailian":
        cache_key = _build_cache_key(food_name, total_calories, protein, carbs, fat, meal_type)

        # 检查 Redis 缓存
        cached = _cache_get(cache_key)
        if cached:
            logger.info("ai_service: cache HIT key=%s", cache_key)
            _write_ai_log(
                engine=cached.engine,
                model=settings.BAILIAN_MODEL,
                prompt_version="ai-bailian-v1",
                response_preview=cached.text[:200],
                latency=cached.latency,
                status="success",
                cache_hit=True,
            )
            return cached

        logger.info("ai_service: cache MISS key=%s", cache_key)
        messages = [
            SYSTEM_MESSAGE,
            build_user_message(
                food_name=food_name,
                meal_type=meal_type,
                total_calories=total_calories,
                protein=protein,
                carbs=carbs,
                fat=fat,
                ocr_text=ocr_text,
                remark=remark,
                estimated=estimated,
            ),
        ]
        result = _call_bailian(messages)

        # 成功则写入缓存
        if result.success and "bailian" in result.engine:
            _cache_set(cache_key, result)

        return result

    # mock 模式
    _write_ai_log(
        engine="ai-mock-v1",
        model="mock",
        prompt_version="ai-mock-v1",
        status="success",
    )
    return AISummaryResult(
        text=MOCK_SUMMARY,
        engine="ai-mock-v1",
        latency="0.0s",
        success=True,
    )
