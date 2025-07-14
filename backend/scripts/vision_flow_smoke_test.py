#!/usr/bin/env python3
"""Vision + Fusion + Confirm 端到端冒烟测试

覆盖流程:
  登录 → 上传图片 → 轮询 SUCCESS → 校验 food_items(source/estimated/confidence)
  → PATCH confirm → 校验 source=manual → 校验汇总同步

用法:
    cd backend
    python scripts/vision_flow_smoke_test.py
    TEST_IMAGE_PATH="D:/test-food.jpg" python scripts/vision_flow_smoke_test.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("缺少 httpx: pip install httpx"); sys.exit(1)

# --- Config ---
API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
BASE = f"{API_BASE}/api"
TEST_PHONE = os.getenv("TEST_PHONE", "13800138000")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "Test123456")
TEST_IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", "")
MAX_POLL = 60
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
TEST_IMAGE = Path(TEST_IMAGE_PATH) if TEST_IMAGE_PATH else (FIXTURE_DIR / "test-food.jpg")

_client: httpx.AsyncClient | None = None
FAILED = False


def log(msg: str, ok: bool = None):
    prefix = {True: "  ✅", False: "  ❌", None: "  →"}[ok]
    print(f"{prefix} {msg}")


async def client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30))
    return _client


async def api_post(path: str, body=None, token=None):
    c = await client()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    return await c.post(f"{BASE}{path}", json=body, headers=headers)


async def api_get(path: str, token=None):
    c = await client()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return await c.get(f"{BASE}{path}", headers=headers)


async def api_patch(path: str, body, token=None):
    c = await client()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {}
    return await c.patch(f"{BASE}{path}", json=body, headers=headers)


def fail(msg):
    global FAILED
    FAILED = True
    log(msg, False)
    sys.exit(1)


# ── Steps ──

async def step_login():
    log("登录...")
    r = await api_post("/auth/login", {"phone": TEST_PHONE, "password": TEST_PASSWORD})
    if r.status_code == 200:
        token = r.json()["access_token"]
        log(f"登录成功: {r.json()['user']['nickname']}", True)
        return token

    # 注册 + 登录
    log("用户不存在，尝试注册...")
    sr = await api_post("/auth/send-code", {"phone": TEST_PHONE, "scene": "register"})
    if sr.status_code != 200 or not sr.json().get("dev_code"):
        fail(f"send-code 失败: {sr.status_code} {sr.text}")
    code = sr.json()["dev_code"]
    rr = await api_post("/auth/register", {"phone": TEST_PHONE, "code": code, "nickname": "vision_test", "password": TEST_PASSWORD})
    if rr.status_code != 201:
        fail(f"注册失败: {rr.status_code} {rr.text}")
    r2 = await api_post("/auth/login", {"phone": TEST_PHONE, "password": TEST_PASSWORD})
    if r2.status_code != 200:
        fail(f"注册后登录失败: {r2.status_code}")
    return r2.json()["access_token"]


def ensure_image():
    if TEST_IMAGE.exists():
        log(f"使用图片: {TEST_IMAGE}", True)
        return
    log("生成测试图片...")
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (400, 400), color=(240, 230, 210))
        d = ImageDraw.Draw(img)
        d.rectangle((60, 60, 340, 340), fill=(210, 200, 170), outline=(150, 140, 100), width=3)
        d.text((120, 180), "Rice Bowl", fill=(80, 60, 40))
        d.text((120, 220), "Chicken", fill=(80, 60, 40))
        img.save(TEST_IMAGE, "JPEG", quality=85)
        log(f"图片已生成: {TEST_IMAGE}", True)
    except ImportError:
        buf = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x09\x09\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9"
        TEST_IMAGE.write_bytes(buf)
        log(f"最小图片已生成: {TEST_IMAGE}", True)


async def step_upload(token: str) -> str:
    log("上传图片...")
    ensure_image()
    with open(TEST_IMAGE, "rb") as f:
        r = await (await client()).post(
            f"{BASE}/foods/upload",
            files={"image": ("test-food.jpg", f, "image/jpeg")},
            data={"meal_type": "lunch", "remark": "vision smoke test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    if r.status_code != 201:
        fail(f"上传失败: {r.status_code} {r.text}")
    task_id = r.json().get("task_id")
    log(f"上传成功: task_id={task_id}", True)
    return task_id


async def step_poll(token: str, task_id: str) -> str:
    log(f"轮询任务 (最多 {MAX_POLL}s)...")
    for i in range(MAX_POLL):
        await asyncio.sleep(1)
        r = await api_get(f"/tasks/{task_id}", token)
        if r.status_code != 200:
            continue
        t = r.json()
        s, p, rid = t.get("status"), t.get("progress_percent", 0), t.get("record_id")
        log(f"  [{i+1}s] status={s} progress={p}% record_id={rid}")
        if s == "SUCCESS" and rid:
            log(f"任务完成: record_id={rid}", True)
            return rid
        if s == "FAILED":
            fail(f"任务失败: {t.get('error_message', 'unknown')}")
    fail("任务超时（未进入 SUCCESS）")


async def step_check_vision_fields(token: str, record_id: str):
    log("校验 food_items 字段...")
    r = await api_get(f"/foods/{record_id}", token)
    if r.status_code != 200:
        fail(f"查询记录失败: {r.status_code}")

    data = r.json().get("data", r.json())
    items = data.get("food_items", [])
    if not items:
        fail("food_items 为空")

    item = items[0]
    checks = [
        ("food_name", item.get("food_name"), lambda v: v, "食物名称"),
        ("source", item.get("source"), lambda v: v in ("vision", "fusion", "ocr"), f"source 为 vision/fusion/ocr, 实际={item.get('source')}"),
        ("estimated", item.get("estimated"), lambda v: v is True or v is False, "estimated 是 bool"),
        ("confidence", item.get("confidence"), lambda v: isinstance(v, (int, float)) and 0 <= v <= 1, f"confidence 0-1, 实际={item.get('confidence')}"),
        ("calories", item.get("calories"), lambda v: isinstance(v, (int, float)), f"calories 数字"),
    ]
    for name, val, cond, desc in checks:
        if not cond(val):
            fail(f"  {name} 校验失败: {desc}")
    log(f"food_name={item.get('food_name')} source={item.get('source')} estimated={item.get('estimated')} ok", True)


async def step_confirm(token: str, record_id: str):
    log("调用 PATCH confirm...")
    body = {
        "items": [{
            "id": "any",
            "food_name": "测试鸡胸肉饭",
            "weight": "1份",
            "category": "mixed",
            "calories": 520,
            "protein": 36,
            "carbs": 65,
            "fat": 12,
        }]
    }
    r = await api_patch(f"/foods/{record_id}/confirm", body, token)
    if r.status_code == 404:
        fail(f"confirm 接口未找到 (404): {r.text}")
    if r.status_code != 200:
        fail(f"confirm 失败: {r.status_code} {r.text}")
    log("confirm 成功", True)


async def step_check_confirm_result(token: str, record_id: str):
    log("校验 confirm 结果...")
    r = await api_get(f"/foods/{record_id}", token)
    data = r.json().get("data", r.json())
    record = data.get("record", {})
    items = data.get("food_items", [])

    item = items[0] if items else {}
    if item.get("source") != "manual":
        fail(f"source 应为 manual, 实际={item.get('source')}")
    log(f"source=manual ✅", True)

    if record.get("total_calories") != 520 or record.get("protein") != 36:
        fail(f"汇总未同步: cal={record.get('total_calories')} pro={record.get('protein')}")
    log(f"total_calories={record.get('total_calories')} protein={record.get('protein')} 汇总已同步", True)


# ── Main ──
async def main():
    print("=" * 50)
    print("  FoodFlow Vision + Confirm Smoke Test")
    print(f"  API: {BASE}")
    print("=" * 50)

    token = await step_login()
    task_id = await step_upload(token)
    record_id = await step_poll(token, task_id)
    await step_check_vision_fields(token, record_id)
    await step_confirm(token, record_id)
    await step_check_confirm_result(token, record_id)

    print("\n" + "=" * 20)
    print("  ✅ Vision flow smoke test passed")
    print("=" * 20)


if __name__ == "__main__":
    asyncio.run(main())
