from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 项目基础配置
    API_PREFIX: str = "/api"
    PROJECT_NAME: str = "FoodFlow API"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:123456@localhost:5432/foodflow_db"

    # JWT
    SECRET_KEY: str = "change-me-to-a-random-secret-key"
    JWT_ALGORITHM: str = "HS256"

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    # SMS 模式: mock | provider
    SMS_MODE: str = "mock"

    # OCR 模式: mock | paddle
    OCR_MODE: str = "mock"

    # AI 模式: mock | bailian
    AI_MODE: str = "mock"
    BAILIAN_API_KEY: str = ""
    BAILIAN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    BAILIAN_MODEL: str = "qwen-plus"
    AI_TIMEOUT_SECONDS: int = 30

    # Vision 模式: mock | bailian
    VISION_MODE: str = "mock"
    BAILIAN_VISION_MODEL: str = "qwen-vl-max"
    VISION_TIMEOUT_SECONDS: int = 30

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
