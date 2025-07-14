import re

from pydantic import BaseModel, field_validator


PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")
CODE_REGEX = re.compile(r"^\d{6}$")


class SendCodeRequest(BaseModel):
    phone: str
    scene: str = "register"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_REGEX.match(v):
            raise ValueError("手机号格式不正确")
        return v


class RegisterRequest(BaseModel):
    phone: str
    code: str
    nickname: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_REGEX.match(v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not CODE_REGEX.match(v):
            raise ValueError("验证码必须是6位数字")
        return v

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("昵称不能为空")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码至少8位")
        return v


class LoginRequest(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_REGEX.match(v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("密码不能为空")
        return v


class UserBasicResponse(BaseModel):
    id: str
    phone: str
    nickname: str
    avatarText: str = ""

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBasicResponse
