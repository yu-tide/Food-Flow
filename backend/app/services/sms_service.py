"""短信验证码服务 — mock / provider"""

import logging
import random
from dataclasses import dataclass

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

CODE_TTL = 300        # 验证码有效期 5 分钟
RATE_TTL = 60         # 发送间隔 60 秒
HOUR_RATE_TTL = 3600  # 每小时限制窗口
MAX_PER_HOUR = 5      # 每小时最多 5 次
MAX_ERRORS = 5        # 最多错误尝试次数
ERROR_TTL = 600       # 错误计数 10 分钟


@dataclass
class SendResult:
    success: bool
    message: str = ""
    dev_code: str | None = None
    blocked: bool = False
    already_registered: bool = False


@dataclass
class VerifyResult:
    valid: bool
    expired: bool = False
    max_errors: bool = False


def _redis():
    return get_redis()


def _code_key(phone: str, scene: str) -> str:
    return f"sms:code:{phone}:{scene}"


def _rate_key(phone: str) -> str:
    return f"sms:rate:{phone}"


def _hour_key(phone: str) -> str:
    return f"sms:hour:{phone}"


def _error_key(phone: str, scene: str) -> str:
    return f"sms:errors:{phone}:{scene}"


# ── mock ──
def _mock_send(phone: str, scene: str) -> SendResult:
    code = f"{random.randint(100000, 999999)}"
    r = _redis()
    if r:
        r.setex(_code_key(phone, scene), CODE_TTL, code)
    logger.info("SMS mock: phone=%s scene=%s code=%s", phone, scene, code)
    return SendResult(success=True, message="验证码已发送", dev_code=code)


# ── provider (TODO: 接入真实短信商) ──
def _provider_send(phone: str, scene: str) -> SendResult:
    code = f"{random.randint(100000, 999999)}"
    r = _redis()
    if r:
        r.setex(_code_key(phone, scene), CODE_TTL, code)
    # TODO: 调用真实短信 API，例如阿里云短信、腾讯云短信
    # response = sms_client.send(phone, template_id, {"code": code})
    # if not response.success: return SendResult(success=False, message="短信发送失败")
    logger.info("SMS provider: phone=%s scene=%s code=%s (TODO: real SMS)", phone[-4:], scene, code)
    return SendResult(success=True, message="验证码已发送")


# ── 频率限制 ──
def _check_rate_limit(phone: str) -> str | None:
    r = _redis()
    if not r:
        return None  # Redis 不可用时不限频
    if r.exists(_rate_key(phone)):
        return "验证码发送太频繁，请 60 秒后再试"
    count = r.get(_hour_key(phone))
    if count and int(count) >= MAX_PER_HOUR:
        return "该手机号每小时最多发送 5 次验证码"
    return None


def _record_send(phone: str):
    r = _redis()
    if not r:
        return
    r.setex(_rate_key(phone), RATE_TTL, "1")
    r.incr(_hour_key(phone))
    r.expire(_hour_key(phone), HOUR_RATE_TTL)


# ── public API ──
def send_code(phone: str, scene: str = "register") -> SendResult:
    limit = _check_rate_limit(phone)
    if limit:
        return SendResult(success=False, message=limit, blocked=True)

    if settings.SMS_MODE == "provider":
        result = _provider_send(phone, scene)
    else:
        result = _mock_send(phone, scene)

    if result.success:
        _record_send(phone)

    return result


def verify_code(phone: str, scene: str, code: str) -> VerifyResult:
    r = _redis()
    if not r:
        return VerifyResult(valid=False)

    error_key = _error_key(phone, scene)
    errors = int(r.get(error_key) or 0)
    if errors >= MAX_ERRORS:
        return VerifyResult(valid=False, max_errors=True)

    stored = r.get(_code_key(phone, scene))
    if stored is None:
        return VerifyResult(valid=False, expired=True)

    if stored != code:
        r.incr(error_key)
        r.expire(error_key, ERROR_TTL)
        return VerifyResult(valid=False)

    # 验证成功 — 删除 code 和 error 记录
    r.delete(_code_key(phone, scene), error_key)
    return VerifyResult(valid=True)
