from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.redis import get_redis

router = APIRouter(tags=["health"])


@router.get("")
async def health_check():
    return {"status": "ok"}


@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "database": "disconnected", "detail": str(e)},
        )


@router.get("/redis")
async def health_redis():
    try:
        get_redis()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "redis": "disconnected", "detail": str(e)},
        )
