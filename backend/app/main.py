import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 所有业务接口统一加 /api 前缀
app.include_router(api_router, prefix="/api")

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# 静态文件服务：挂载上传目录
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    return {"message": "FoodFlow API is running"}