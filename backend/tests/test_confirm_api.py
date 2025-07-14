"""Confirm API 服务层测试（需要 PostgreSQL + 稳定事件循环）"""
import uuid

import pytest
from sqlalchemy import select

from app.db.session import async_session
from app.models.food_item import FoodItem
from app.models.food_record import FoodRecord
from app.services.food_service import confirm_food_record

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skip(reason="需要 PostgreSQL 连接 + 稳定 asyncpg 事件循环"),
]


async def _create_record(db, rid: str, uid: str):
    """先创建 record（flush 后再创建 item 以避免 FK 约束问题）"""
    record = FoodRecord(
        id=rid, user_id=uid, meal_type="lunch",
        total_calories=100, protein=10, carbohydrate=20, fat=5,
        status_label="分析完成",
    )
    db.add(record)
    await db.flush()  # 先 flush 生成 ID

    item = FoodItem(
        id=str(uuid.uuid4()), record_id=rid,
        food_name="test food", calories=100, protein=10, carbs=20, fat=5,
    )
    db.add(item)
    await db.commit()
    return record


async def _cleanup(db, rid: str):
    from sqlalchemy import text
    await db.execute(text(f"DELETE FROM food_items WHERE record_id = '{rid}'"))
    await db.execute(text(f"DELETE FROM food_records WHERE id = '{rid}'"))
    await db.commit()


async def test_confirm_updates_items():
    async with async_session() as db:
        rid, uid = str(uuid.uuid4()), str(uuid.uuid4())
        await _create_record(db, rid, uid)

        await confirm_food_record(db, rid, uid, [{
            "food_name": "鸡胸肉饭", "weight": "1份", "category": "mixed",
            "calories": 520, "protein": 36, "carbs": 65, "fat": 12,
        }])

        r = await db.execute(select(FoodItem).where(FoodItem.record_id == rid))
        items = r.scalars().all()
        assert len(items) == 1
        assert items[0].food_name == "鸡胸肉饭"
        assert items[0].source == "manual"
        assert items[0].estimated is False

        rec = (await db.execute(select(FoodRecord).where(FoodRecord.id == rid))).scalar_one()
        assert rec.total_calories == 520

        await _cleanup(db, rid)


async def test_confirm_multi_items():
    async with async_session() as db:
        rid, uid = str(uuid.uuid4()), str(uuid.uuid4())
        await _create_record(db, rid, uid)

        await confirm_food_record(db, rid, uid, [
            {"food_name": "米饭", "calories": 174, "protein": 3, "carbs": 38, "fat": 0},
            {"food_name": "鸡胸肉", "calories": 266, "protein": 62, "carbs": 0, "fat": 2},
        ])

        items = (await db.execute(
            select(FoodItem).where(FoodItem.record_id == rid).order_by(FoodItem.sort_order)
        )).scalars().all()
        assert len(items) == 2
        assert all(it.source == "manual" for it in items)

        rec = (await db.execute(select(FoodRecord).where(FoodRecord.id == rid))).scalar_one()
        assert rec.total_calories == 440

        await _cleanup(db, rid)


async def test_confirm_wrong_user_denied():
    async with async_session() as db:
        rid, uid = str(uuid.uuid4()), str(uuid.uuid4())
        await _create_record(db, rid, uid)

        with pytest.raises(ValueError, match="无权"):
            await confirm_food_record(db, rid, "wrong-user-id", [{"food_name": "x"}])

        await _cleanup(db, rid)
