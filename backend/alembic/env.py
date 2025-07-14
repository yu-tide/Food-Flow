import sys
from pathlib import Path
# 将 backend 目录加入 Python 路径，确保 alembic 能找到 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.base import Base

# 导入所有模型，确保 Alembic 能检测到所有表结构（必须导入所有模型文件）
import app.models  # noqa: F401

# 读取 alembic 配置
config = context.config

# 从 settings 中获取数据库 URL，覆盖 alembic.ini 中的配置
# 自动使用你配置中指向 foodflow_db 的连接地址
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据：你的所有模型的基类
target_metadata = Base.metadata


def run_migrations_offline():
    """离线模式迁移：不需要连接数据库，直接生成 SQL"""
    # 离线模式需要同步 URL，自动把 asyncpg 协议转换为标准 PostgreSQL 协议
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # 自动比较字段类型变化，生成更准确的迁移
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """在线模式迁移：异步连接数据库执行迁移"""
    # 使用你的 foodflow_db 连接 URL 创建异步引擎
    connectable = create_async_engine(settings.DATABASE_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
