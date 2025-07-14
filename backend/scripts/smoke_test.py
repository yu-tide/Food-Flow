#!/usr/bin/env python3
"""FoodFlow 自动化冒烟测试

自动验证主链路：准备用户 → 登录 → 上传图片 → 轮询任务 → 等待 SUCCESS → 查询结果

用法:
    cd backend
    python scripts/smoke_test.py                          # 默认 API_BASE_URL=http://127.0.0.1:8000
    API_BASE_URL=http://localhost:8000 python scripts/smoke_test.py

环境变量:
    API_BASE_URL    后端地址，默认 http://127.0.0.1:8000
    TEST_PHONE      测试手机号，默认 13800138000
    TEST_PASSWORD   测试密码，默认 Test123456
"""

import asyncio
import io
import os
import sys
import time
from pathlib import Path

# Fix Windows GBK encoding for emoji output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("❌ 缺少 httpx，请执行: pip install httpx")
    sys.exit(1)

# --- Config ---
API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
API_PREFIX = "/api"
BASE = f"{API_BASE}{API_PREFIX}"

TEST_PHONE = os.getenv("TEST_PHONE", "13800138000")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "Test123456")
TEST_IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", "")
TEST_NICKNAME = "冒烟测试用户"

MAX_POLL_SECONDS = 60
POLL_INTERVAL = 1.0

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
TEST_IMAGE = Path(TEST_IMAGE_PATH) if TEST_IMAGE_PATH else (FIXTURE_DIR / "test-food.jpg")

# --- Helpers ---
_client: httpx.AsyncClient | None = None


def log(msg: str, level: str = "info"):
    prefix = {"info": "  →", "ok": "  ✅", "fail": "  ❌", "warn": "  ⚠️"}.get(level, "  →")
    print(f"{prefix} {msg}")


async def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(15))
    return _client


async def api_post(path: str, body: dict | None = None, token: str | None = None):
    c = await client()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    res = await c.post(f"{BASE}{path}", json=body, headers=headers) if body else await c.post(f"{BASE}{path}", headers=headers)
    return res


async def api_get(path: str, token: str | None = None):
    c = await client()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return await c.get(f"{BASE}{path}", headers=headers)


async def api_upload(path: str, files: dict, data: dict, token: str | None = None):
    c = await client()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return await c.post(f"{BASE}{path}", files=files, data=data, headers=headers)


# --- Steps ---

async def step_check_backend():
    """1. 检查后端是否可用"""
    log("检查后端是否可用...")
    try:
        c = await client()
        res = await c.get(f"{API_BASE}/")
        if res.status_code == 200:
            log("后端可用", "ok")
            return True
        else:
            log(f"后端返回 {res.status_code}", "fail")
            return False
    except Exception as e:
        log(f"后端不可用: {e}", "fail")
        log("请确认 uvicorn 已启动: cd backend && uvicorn app.main:app --reload", "warn")
        raise SystemExit(1)


async def step_prepare_user():
    """2. 准备测试用户：先登录，失败则注册，再失败则 DB seed"""
    log("准备测试用户...")

    # Try login first
    res = await api_post("/auth/login", {"phone": TEST_PHONE, "password": TEST_PASSWORD})
    if res.status_code == 200:
        data = res.json()
        log(f"登录成功: {data['user']['nickname']}", "ok")
        return data["access_token"]

    if res.status_code == 401:
        log("用户不存在或密码错误，尝试注册...")

        # Try register via API (needs Redis for dev_code)
        try:
            send_res = await api_post("/auth/send-code", {"phone": TEST_PHONE, "scene": "register"})
            if send_res.status_code == 200:
                send_data = send_res.json()
                dev_code = send_data.get("dev_code")
                if dev_code:
                    log(f"获取到 dev_code: {dev_code}")
                    reg_res = await api_post("/auth/register", {
                        "phone": TEST_PHONE,
                        "code": dev_code,
                        "nickname": TEST_NICKNAME,
                        "password": TEST_PASSWORD,
                    })
                    if reg_res.status_code == 201:
                        log("注册成功", "ok")
                        res2 = await api_post("/auth/login", {"phone": TEST_PHONE, "password": TEST_PASSWORD})
                        return res2.json()["access_token"]
                    log(f"注册失败: {reg_res.status_code} {reg_res.text}", "fail")
            elif send_res.status_code == 409:
                log("手机号已注册但密码不对，重置密码...", "warn")
            elif send_res.status_code == 503:
                log("Redis 不可用，无法发送验证码", "warn")
        except Exception as e:
            log(f"注册流程异常: {e}", "warn")

        # DB seed fallback
        log("通过数据库创建/重置测试用户...")
        try:
            import asyncio as _asyncio
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from app.core.config import settings as app_settings
            from app.core.security import hash_password
            from app.models.user import User

            engine = create_async_engine(app_settings.DATABASE_URL)
            sf = async_sessionmaker(engine, expire_on_commit=False)

            async with sf() as db:
                hashed = hash_password(TEST_PASSWORD)
                result = await db.execute(select(User).where(User.phone == TEST_PHONE))
                user = result.scalar_one_or_none()
                if user:
                    user.hashed_password = hashed
                    user.nickname = TEST_NICKNAME
                    await db.commit()
                else:
                    user = User(phone=TEST_PHONE, nickname=TEST_NICKNAME, hashed_password=hashed, avatar_text=TEST_NICKNAME[0])
                    db.add(user)
                    await db.commit()
                log(f"DB 用户就绪: id={user.id}", "ok")
            await engine.dispose()

            res3 = await api_post("/auth/login", {"phone": TEST_PHONE, "password": TEST_PASSWORD})
            if res3.status_code == 200:
                return res3.json()["access_token"]
            log(f"DB 用户创建后登录仍失败: {res3.status_code}", "fail")
        except Exception as e:
            log(f"DB seed 失败: {e}", "fail")

    log(f"登录失败: {res.status_code} {res.text}", "fail")
    raise SystemExit(2)


def generate_test_image():
    """生成测试图片到 fixtures/test-food.jpg"""
    if TEST_IMAGE.exists():
        log(f"使用已有测试图片: {TEST_IMAGE}", "info")
        return

    log("生成测试图片...")
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (400, 400), color=(255, 240, 220))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(50, 50), (350, 350)], fill=(200, 220, 180), outline=(100, 150, 80), width=3)
        draw.text((120, 160), "🍚 Rice", fill=(50, 50, 50))
        draw.text((120, 200), "🍗 Chicken", fill=(50, 50, 50))
        draw.text((120, 240), "🥦 Broccoli", fill=(50, 50, 50))
        draw.text((120, 280), "🥚 Egg", fill=(50, 50, 50))
        img.save(TEST_IMAGE, "JPEG", quality=85)
        log(f"测试图片已生成: {TEST_IMAGE}", "ok")
    except ImportError:
        log("Pillow 未安装，生成最小 JPEG...", "warn")
        # Minimal valid JPEG
        minimal_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x09\x09"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
            b"\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f"
            b"\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01"
            b"\x00\x00?\x00\xd2\xcf \xff\xd9"
        )
        TEST_IMAGE.write_bytes(minimal_jpeg)
        log(f"最小测试图片已生成: {TEST_IMAGE}", "ok")


async def step_upload(token: str) -> str:
    """3. 上传测试图片，返回 task_id"""
    log("上传测试图片...")
    generate_test_image()

    with open(TEST_IMAGE, "rb") as f:
        files = {"image": ("test-food.jpg", f, "image/jpeg")}
        data = {"meal_type": "lunch", "remark": "smoke test"}
        res = await api_upload("/foods/upload", files=files, data=data, token=token)

    if res.status_code == 201:
        task_id = res.json().get("task_id")
        log(f"上传成功: task_id={task_id}", "ok")
        return task_id

    log(f"上传失败: {res.status_code} {res.text}", "fail")
    raise SystemExit(3)


async def step_poll_task(token: str, task_id: str) -> str:
    """4. 轮询任务状态，返回 record_id"""
    log(f"轮询任务 {task_id}（最多 {MAX_POLL_SECONDS}s）...")

    for i in range(MAX_POLL_SECONDS):
        await asyncio.sleep(POLL_INTERVAL)
        res = await api_get(f"/tasks/{task_id}", token)

        if res.status_code == 404:
            # Task endpoint might be at /foods/tasks/{task_id}
            res = await api_get(f"/foods/tasks/{task_id}", token)
            if res.status_code == 404:
                log(f"任务接口 404（轮询 {i+1}s）", "warn")
                continue

        if not res.is_success:
            log(f"任务查询失败: {res.status_code}", "warn")
            continue

        task = res.json()
        status = task.get("status")
        progress = task.get("progress_percent", 0)
        record_id = task.get("record_id")

        elapsed = i + 1
        log(f"[{elapsed}s] status={status} progress={progress}% record_id={record_id}")

        if status == "SUCCESS" and record_id:
            log(f"任务完成: record_id={record_id}", "ok")
            return record_id

        if status == "FAILED":
            err = task.get("error_message", "未知错误")
            log(f"任务失败: {err}", "fail")
            raise SystemExit(4)

    log("任务超时（未进入 SUCCESS），请确认 Redis 和 Celery worker 已启动", "fail")
    log("  cd backend && celery -A app.worker worker --loglevel=info -P solo", "warn")
    raise SystemExit(5)


async def step_check_result(token: str, record_id: str):
    """5. 查询分析结果并校验字段"""
    log(f"查询分析结果: /api/foods/{record_id}...")
    res = await api_get(f"/foods/{record_id}", token)

    if res.status_code == 404:
        log("结果不存在（可能权限问题或 record_id 不对）", "fail")
        raise SystemExit(6)
    if not res.is_success:
        log(f"查询失败: {res.status_code}", "fail")
        raise SystemExit(6)

    body = res.json()
    data = body.get("data", body)
    record = data.get("record", {})

    checks = [
        ("total_calories", record.get("total_calories")),
        ("protein", record.get("protein")),
        ("carbohydrate", record.get("carbohydrate")),
        ("fat", record.get("fat")),
        ("food_items", data.get("food_items")),
        ("image_url", record.get("image_url")),
    ]

    for name, val in checks:
        if val is None:
            log(f"字段缺失: {name}", "fail")
            raise SystemExit(7)
        log(f"  {name}: {val}", "ok" if name != "food_items" else "info")

    log("所有字段校验通过", "ok")


async def step_check_records_list(token: str):
    """6. 查询 records 列表"""
    log("查询记录列表: /api/foods?range=week...")
    res = await api_get("/foods?range=week", token)
    if res.status_code == 401:
        log("未授权 (401)", "fail")
        raise SystemExit(8)
    if not res.is_success:
        log(f"查询失败: {res.status_code}", "fail")
        raise SystemExit(8)

    body = res.json()
    items = body.get("data", [])
    log(f"records count: {len(items)}", "ok")


async def step_check_dashboard(token: str):
    """7. 查询 dashboard summary"""
    log("查询仪表盘: /api/dashboard/summary...")
    res = await api_get("/dashboard/summary", token)
    if res.status_code == 401:
        log("未授权 (401)", "fail")
        raise SystemExit(9)
    if not res.is_success:
        log(f"查询失败: {res.status_code}", "fail")
        raise SystemExit(9)

    body = res.json()
    today = body.get("today", {})
    macros = body.get("macros", [])
    log(f"today consumed={today.get('consumedCalories')} macros={len(macros)} items", "ok")


async def step_check_weekly(token: str):
    """8. 查询每周统计"""
    log("查询每周统计: /api/statistics/weekly...")
    res = await api_get("/statistics/weekly", token)
    if res.status_code == 401:
        log("未授权 (401)", "fail")
        raise SystemExit(10)
    if not res.is_success:
        log(f"查询失败: {res.status_code}", "fail")
        raise SystemExit(10)

    body = res.json()
    daily = body.get("daily_calories", [])
    rec_cnt = body.get("record_count", 0)
    log(f"daily_calories={len(daily)} days record_count={rec_cnt}", "ok")


# --- Main ---

async def main():
    print("=" * 50)
    print("  FoodFlow Smoke Test")
    print(f"  API: {BASE}")
    print("=" * 50)

    await step_check_backend()
    token = await step_prepare_user()
    task_id = await step_upload(token)
    record_id = await step_poll_task(token, task_id)
    await step_check_result(token, record_id)
    await step_check_records_list(token)
    await step_check_dashboard(token)
    await step_check_weekly(token)

    print()
    print("=" * 20)
    print("  ✅ Smoke test passed")
    print("=" * 20)


if __name__ == "__main__":
    asyncio.run(main())
