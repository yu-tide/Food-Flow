from pydantic import BaseModel


class RAGSearchRequest(BaseModel):
    query: str = ""
    top_k: int = 5


class RAGSearchResult(BaseModel):
    title: str
    content: str
    score: float
    source_type: str


class RAGSearchResponse(BaseModel):
    results: list[RAGSearchResult] = []
