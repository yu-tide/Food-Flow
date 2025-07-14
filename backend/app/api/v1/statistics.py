from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.statistics_service import get_weekly_stats

router = APIRouter(prefix="/statistics", tags=["每周统计"])


@router.get("/weekly")
async def weekly_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_weekly_stats(db, current_user)
