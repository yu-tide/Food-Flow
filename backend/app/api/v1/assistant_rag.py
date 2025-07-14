"""RAG search endpoint — keyword-only Phase 9."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.assistant_rag import RAGSearchRequest, RAGSearchResponse
from app.services.rag_service import search_knowledge

router = APIRouter(prefix="/assistant/rag", tags=["AI 助手 RAG"])


@router.post("/search", response_model=RAGSearchResponse)
async def rag_search(
    body: RAGSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await search_knowledge(db, body.query, body.top_k)
    return RAGSearchResponse(results=results)
