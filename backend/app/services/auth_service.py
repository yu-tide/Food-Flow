from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.services.sms_service import send_code as _send_sms, verify_code as _verify_sms


async def send_code(db: AsyncSession, phone: str, scene: str) -> dict:
    """发送验证码。Redis 不可用时抛异常。"""
    # 注册场景检查手机号是否已注册
    if scene == "register":
        result = await db.execute(select(User).where(User.phone == phone))
        if result.scalar_one_or_none() is not None:
            return {"already_registered": True}

    sms_result = _send_sms(phone, scene)
    if not sms_result.success:
        raise RuntimeError(sms_result.message)

    response = {"message": sms_result.message}
    if sms_result.dev_code:
        response["dev_code"] = sms_result.dev_code
    if sms_result.blocked:
        response["blocked"] = True
    return response


async def verify_code(phone: str, scene: str, code: str) -> bool:
    """验证验证码是否正确，验证成功后删除。"""
    result = _verify_sms(phone, scene, code)
    return result.valid


async def register_user(db: AsyncSession, phone: str, nickname: str, password: str) -> User:
    avatar_text = nickname[0] if nickname else ""

    user = User(
        phone=phone,
        nickname=nickname,
        hashed_password=hash_password(password),
        avatar_text=avatar_text,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def authenticate_user(db: AsyncSession, phone: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()

    if user is None:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


def create_login_response(user: User) -> dict:
    token = create_access_token(str(user.id))

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "phone": user.phone,
            "nickname": user.nickname,
            "avatarText": user.avatar_text or "",
        },
    }
