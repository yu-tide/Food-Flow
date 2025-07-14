#!/usr/bin/env python3
r"""PaddleOCR debug script - compare ocr() and predict()

Usage:
    python scripts/debug_ocr.py <image_path>
    python scripts/debug_ocr.py "D:/FoodFlow/backend/uploads/user-uuid/file.jpg"
"""
import os
import sys
from pathlib import Path

IMAGE = sys.argv[1] if len(sys.argv) > 1 else None
if not IMAGE:
    print("用法: python scripts/debug_ocr.py <image_path>")
    sys.exit(1)

# ── 文件信息 ──
abs_path = str(Path(IMAGE).resolve())
print(f"输入路径:     {IMAGE}")
print(f"绝对路径:     {abs_path}")
print(f"文件存在:     {os.path.isfile(abs_path)}")
print(f"文件大小:     {os.path.getsize(abs_path) if os.path.isfile(abs_path) else 'N/A'} bytes")

try:
    from PIL import Image as PILImage
    img = PILImage.open(abs_path)
    print(f"图片尺寸:     {img.size}")
    print(f"图片模式:     {img.mode}")
except ImportError:
    print("图片尺寸:     Pillow not installed")
except Exception as e:
    print(f"图片打开失败: {e}")

# ── Paddle 版本 ──
try:
    import paddle
    print(f"paddle 版本:  {paddle.__version__}")
except ImportError:
    print("paddle 版本:  未安装")

# ── PaddleOCR import ──
try:
    from paddleocr import PaddleOCR
    print("paddleocr:    import OK")
except ImportError as e:
    print(f"paddleocr:    import FAILED: {e}")
    sys.exit(1)

print("=" * 60)

# ── 方式 A: ocr() ──
print("\n── 方式 A: PaddleOCR.ocr() ──")
try:
    ocr = PaddleOCR(lang="ch", use_angle_cls=True)
    result_a = ocr.ocr(abs_path)
    print(f"result type:     {type(result_a).__name__}")
    print(f"result len:      {len(result_a) if result_a else 0}")

    if result_a and result_a[0] is not None:
        page0 = result_a[0]
        print(f"result[0] type:  {type(page0).__name__}")
        print(f"result[0] len:   {len(page0) if hasattr(page0, '__len__') else 'N/A'}")

        rep = repr(page0)
        print(f"result[0] repr (first 2000 chars):\n{rep[:2000]}")

        lines_a = []
        for item in page0:
            if isinstance(item, dict):
                print(f"\n  [dict] keys: {list(item.keys())}")
                for k in ("rec_text", "text", "recognized_text", "transcription"):
                    v = item.get(k)
                    if v:
                        print(f"  {k}: {v}")
                t = item.get("rec_text") or item.get("text") or ""
                if t and isinstance(t, str):
                    lines_a.append(t.strip())
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                inner = item[1]
                if isinstance(inner, (list, tuple)) and len(inner) >= 1:
                    t = str(inner[0])
                elif isinstance(inner, str):
                    t = inner
                else:
                    t = ""
                if t:
                    lines_a.append(t.strip())
                    print(f"  [list] text: {t}")

        print(f"\nlines_count (ocr): {len(lines_a)}")
        print(f"lines (ocr):       {lines_a}")
    else:
        print("result[0] is None or empty → ocr() returned nothing")
        lines_a = []

except Exception as e:
    print(f"ocr() FAILED: {e}")
    import traceback
    traceback.print_exc()
    lines_a = []

print("\n── 方式 B: PaddleOCR.predict() ──")
try:
    ocr2 = PaddleOCR(lang="ch")
    result_b = ocr2.predict(abs_path)
    print(f"result type:     {type(result_b).__name__}")

    rep_b = repr(result_b)
    print(f"result repr (first 2000 chars):\n{rep_b[:2000]}")

    lines_b = []

    # predict() 返回 PaddleOCR 的 OCRResult 对象
    # 尝试多种方式提取文本
    if hasattr(result_b, 'json'):
        try:
            j = result_b.json
            print(f"\nresult.json type: {type(j).__name__}")
            rep_j = repr(j)[:2000]
            print(f"result.json: {rep_j}")
        except Exception as e:
            print(f"result.json failed: {e}")

    # 尝试 rec_texts_ 属性（PaddleOCR 内部）
    for attr in ('rec_texts_', 'texts', 'rec_texts', 'data', '_data'):
        if hasattr(result_b, attr):
            val = getattr(result_b, attr)
            print(f"\nresult.{attr}: {repr(val)[:500]}")

    # 尝试遍历 result_b 如果是可迭代的
    if hasattr(result_b, '__iter__'):
        try:
            items = list(result_b)
            print(f"\nresult 可迭代, len={len(items)}")
            for i, item in enumerate(items[:10]):
                if isinstance(item, dict):
                    t = item.get("rec_text") or item.get("text") or ""
                    if t:
                        lines_b.append(str(t).strip())
                print(f"  [{i}] type={type(item).__name__} rep={repr(item)[:200]}")
        except Exception as e:
            print(f"  iter failed: {e}")

    print(f"\nlines_count (predict): {len(lines_b)}")
    print(f"lines (predict):       {lines_b}")

except Exception as e:
    print(f"predict() FAILED: {e}")
    import traceback
    traceback.print_exc()
    lines_b = []

# ── 结论 ──
print("\n" + "=" * 60)
print("结论")
print("─" * 30)
print(f"ocr()     识别到文字: {'YES' if lines_a else 'NO'}  ({len(lines_a)} lines)")
print(f"predict() 识别到文字: {'YES' if lines_b else 'NO'}  ({len(lines_b)} lines)")

if lines_a:
    print("推荐: 使用 ocr.ocr()（当前方式）")
elif lines_b:
    print("推荐: 改用 ocr.predict()（需要修改 ocr_service.py）")
else:
    print("两者都为空 → 检查图片质量（清晰度/文字大小/对比度）或尝试预处理")
