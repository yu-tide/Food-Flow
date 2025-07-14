import os
import uuid
from datetime import datetime, timezone

from fastapi import UploadFile

from app.core.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def get_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower()


def validate_image_file(file: UploadFile) -> None:
    """校验图片文件类型和大小。不合法时抛出 ValueError。"""

    # 类型校验
    if file.content_type and file.content_type not in {
        "image/jpeg", "image/png", "image/jpg", "image/webp",
    }:
        raise ValueError("文件类型不支持，仅允许 JPG/PNG/WebP")

    # 扩展名校验
    ext = get_extension(file.filename or "unknown.jpg")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {ext}")

    # 大小校验：读取到内存检查大小后需要 seek 回开头
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)

    if size == 0:
        raise ValueError("文件为空")

    if size > settings.MAX_UPLOAD_SIZE:
        raise ValueError(f"文件大小不能超过 {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB")


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"


async def save_upload(file: UploadFile, user_id: str) -> dict:
    """
    将上传文件保存到 UPLOAD_DIR/{user_id}/{uuid}.{ext}
    返回 {"filename", "image_url", "file_size_bytes", "file_size", "image_format"}
    """
    ext = get_extension(file.filename or "unknown.jpg")
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    file_id = uuid.uuid4()
    relative_dir = f"{user_id}"
    abs_dir = os.path.join(settings.UPLOAD_DIR, relative_dir)
    os.makedirs(abs_dir, exist_ok=True)

    stored_name = f"{file_id}{ext}"
    abs_path = os.path.join(abs_dir, stored_name)

    content = await file.read()
    file_size_bytes = len(content)

    with open(abs_path, "wb") as f:
        f.write(content)

    image_url = f"/uploads/{relative_dir}/{stored_name}"

    return {
        "filename": file.filename or "unknown.jpg",
        "image_url": image_url,
        "file_size_bytes": file_size_bytes,
        "file_size": format_file_size(file_size_bytes),
        "image_format": ext.lstrip(".").upper(),
    }