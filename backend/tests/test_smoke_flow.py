"""FoodFlow 冒烟测试 — pytest 版本

用法:
    cd backend
    pytest tests/test_smoke_flow.py -s -v

环境变量:
    API_BASE_URL    后端地址，默认 http://127.0.0.1:8000
    TEST_PHONE      测试手机号
    TEST_PASSWORD   测试密码
"""

import os
import sys
from pathlib import Path

import pytest

# smoke_test.py 和 backend/ 在同一层级
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.smoke_test import (
    API_BASE,
    BASE,
    TEST_PASSWORD,
    TEST_PHONE,
    generate_test_image,
    step_check_backend,
    step_check_result,
    step_poll_task,
    step_prepare_user,
    step_upload,
)

_token: str | None = None
_task_id: str | None = None
_record_id: str | None = None


@pytest.mark.asyncio
async def test_01_backend_alive():
    assert await step_check_backend()


@pytest.mark.asyncio
async def test_02_login_or_register():
    global _token
    _token = await step_prepare_user()
    assert _token


@pytest.mark.asyncio
async def test_03_upload():
    global _task_id
    assert _token
    generate_test_image()
    _task_id = await step_upload(_token)
    assert _task_id


@pytest.mark.asyncio
async def test_04_poll_until_success():
    assert _token and _task_id
    global _record_id
    _record_id = await step_poll_task(_token, _task_id)
    assert _record_id


@pytest.mark.asyncio
async def test_05_verify_result():
    assert _token and _record_id
    await step_check_result(_token, _record_id)
