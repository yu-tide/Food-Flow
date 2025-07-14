"""OCR 识别服务 — 支持 mock / paddle 两种模式"""
import logging
import os
import time
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---- mock OCR ---- 保留现有行为，保证向后兼容
MOCK_OCR_TEXT = "米饭、鸡胸肉、西兰花、鸡蛋"
MOCK_OCR_LINES = ["米饭", "鸡胸肉", "西兰花", "鸡蛋"]


@dataclass
class OCRResult:
    text: str           # 单行拼接文本
    lines: list[str]    # 识别出的每一行
    engine: str         # "mock" | "paddle"
    success: bool
    error_message: str | None = None


def _image_url_to_path(image_url: str | None) -> str | None:
    """将 image_url 转换为本地绝对路径。

    image_url 例如：/uploads/user-uuid/file-uuid.jpg
    转换后：<UPLOAD_DIR>/user-uuid/file-uuid.jpg
    """
    if not image_url:
        return None
    if image_url.startswith("/uploads/"):
        rel = image_url[len("/uploads/"):]
        return os.path.join(settings.UPLOAD_DIR, rel)
    # 外部 URL 暂不支持下载
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return None
    return image_url


def _run_mock(image_path: str | None) -> OCRResult:
    """mock 模式：返回固定文本"""
    logger.info("OCR engine=mock image=%s", image_path)
    time.sleep(0.5)  # 模拟识别延迟
    return OCRResult(
        text=MOCK_OCR_TEXT,
        lines=MOCK_OCR_LINES,
        engine="mock",
        success=True,
    )


def _run_paddle(image_path: str | None) -> OCRResult:
    """paddle 模式：真实调用 PaddleOCR"""
    if not image_path or not os.path.isfile(image_path):
        return OCRResult(
            text="",
            lines=[],
            engine="paddle",
            success=False,
            error_message=f"图片文件不存在: {image_path}",
        )

    try:
        from paddleocr import PaddleOCR  # 延迟 import，不影响 mock 模式
    except ImportError as e:
        return OCRResult(
            text="",
            lines=[],
            engine="paddle",
            success=False,
            error_message=f"PaddleOCR 未安装: {e}",
        )

    logger.info("PaddleOCR image_path=%s file_exists=%s size=%d",
                image_path, os.path.isfile(image_path), os.path.getsize(image_path) if os.path.isfile(image_path) else 0)

    try:
        ocr = PaddleOCR(lang="ch", use_angle_cls=True)
        result = ocr.ocr(image_path)
        logger.info("PaddleOCR raw result type=%s len=%s result[0] is None=%s",
                    type(result).__name__, len(result) if result else 0,
                    result[0] is None if (result and result[0]) else True)
    except Exception as e:
        logger.exception("PaddleOCR 初始化或识别失败")
        return OCRResult(
            text="",
            lines=[],
            engine="paddle",
            success=False,
            error_message=f"PaddleOCR 运行异常: {e}",
        )

    lines: list[str] = []

    if result and result[0]:
        page = result[0]
        page_type = type(page).__name__

        # PaddleOCR 3.x: page-level OCRResult has rec_texts (list[str])
        rec_texts = None
        if hasattr(page, "rec_texts"):
            rec_texts = page.rec_texts
        elif hasattr(page, "get"):
            rec_texts = page.get("rec_texts") or page.get("rec_text")

        if rec_texts and isinstance(rec_texts, list):
            lines = [str(t).strip() for t in rec_texts if t and str(t).strip()]
            logger.info("PaddleOCR rec_texts (page-level) count=%d", len(lines))
        else:
            # Fallback: iterate items (PaddleOCR 2.x format or per-item dict)
            logger.info("PaddleOCR page type=%s no rec_texts, iterating items count=%d",
                        page_type, len(page) if hasattr(page, '__len__') else 0)
            for item in page:
                t = ""
                # dict-like (PaddleOCR 3.x per-item)
                if hasattr(item, "get"):
                    t = item.get("rec_text") or item.get("text") or ""
                elif isinstance(item, dict):
                    t = item.get("rec_text") or item.get("text") or ""
                # list/tuple (PaddleOCR 2.x: [bbox, (text, confidence)])
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    inner = item[1]
                    t = inner[0] if isinstance(inner, (list, tuple)) else str(inner)
                if t and isinstance(t, str) and t.strip():
                    lines.append(t.strip())

    text = "、".join(lines) if lines else ""

    logger.info("OCR engine=paddle lines=%d text=%s", len(lines), text[:100])
    return OCRResult(
        text=text,
        lines=lines,
        engine="paddle",
        success=True,
    )


def recognize_image_text(image_url: str | None) -> OCRResult:
    """统一入口：根据 OCR_MODE 调用对应引擎"""
    image_path = _image_url_to_path(image_url)

    if settings.OCR_MODE == "paddle":
        return _run_paddle(image_path)

    # 默认 mock
    return _run_mock(image_path)
