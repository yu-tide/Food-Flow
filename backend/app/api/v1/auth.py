from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    SendCodeRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/send-code")
async def send_code(
    request: SendCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await auth_service.send_code(
            db=db,
            phone=request.phone,
            scene=request.scene,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    if result.get("blocked"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证码发送太频繁，请稍后再试",
        )

    if result.get("already_registered"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="手机号已注册",
        )

    response = {
        "message": "验证码已发送"
    }

    dev_code = result.get("dev_code")
    if dev_code:
        response["dev_code"] = dev_code

    return response


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    code_valid = await auth_service.verify_code(
        phone=request.phone,
        scene="register",
        code=request.code,
    )

    if not code_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        )

    try:
        user = await auth_service.register_user(
            db=db,
            phone=request.phone,
            nickname=request.nickname,
            password=request.password,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="手机号已注册",
        )

    return {
        "message": "注册成功",
        "user": {
            "id": str(user.id),
            "phone": user.phone,
            "nickname": user.nickname,
            "avatarText": user.avatar_text or "",
        },
    }


@router.post("/login")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.authenticate_user(
        db=db,
        phone=request.phone,
        password=request.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
        )

    return auth_service.create_login_response(user)