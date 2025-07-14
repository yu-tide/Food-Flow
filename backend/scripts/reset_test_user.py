"""重置测试用户脚本
用法: cd backend && python scripts/reset_test_user.py
效果: 创建或重置 phone=13800138000 的测试用户，密码 12345678
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.user import User
from app.core.config import settings
from app.core.security import hash_password

TEST_PHONE = "13800138000"
TEST_PASSWORD = "12345678"
TEST_NICKNAME = "测试用户"


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        hashed = hash_password(TEST_PASSWORD)

        result = await db.execute(select(User).where(User.phone == TEST_PHONE))
        user = result.scalar_one_or_none()

        if user:
            user.hashed_password = hashed
            user.nickname = TEST_NICKNAME
            await db.commit()
            print(f"[OK] 已更新用户 phone={TEST_PHONE} 的密码哈希")
        else:
            user = User(
                phone=TEST_PHONE,
                nickname=TEST_NICKNAME,
                hashed_password=hashed,
                avatar_text=TEST_NICKNAME[0],
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"[OK] 已创建用户 phone={TEST_PHONE} id={user.id}")

        print(f"     验证哈希: {hash_password(TEST_PASSWORD)[:30]}...")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
