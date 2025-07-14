"""LocalEmbedder — 本地语义嵌入（基于 sentence-transformers）

当 sentence-transformers 不可用时静默回退到关键字匹配。
"""

from __future__ import annotations
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class LocalEmbedder:
    """本地嵌入服务 — 单例，懒加载"""

    _instance: LocalEmbedder | None = None
    _model: Any = None
    _available: bool = False

    def __new__(cls) -> LocalEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._try_load()
        return cls._instance

    def _try_load(self) -> None:
        """尝试加载 sentence-transformers 模型，静默回退"""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._available = True
            logger.info("LocalEmbedder: all-MiniLM-L6-v2 loaded (384d)")
        except ImportError:
            logger.info("LocalEmbedder: sentence-transformers not installed, using keyword fallback")
        except Exception as e:
            logger.warning("LocalEmbedder: load failed: %s", e)

    @property
    def available(self) -> bool:
        return self._available

    def embed(self, text: str) -> list[float] | None:
        """返回 384 维向量，不可用时返回 None"""
        if not self._available or not self._model:
            return None
        try:
            return self._model.encode(text).tolist()
        except Exception as e:
            logger.warning("LocalEmbedder: encode failed: %s", e)
            return None

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """余弦相似度"""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5 or 1.0
        nb = sum(y * y for y in b) ** 0.5 or 1.0
        return dot / (na * nb)

    def rank_by_keyword(self, query: str, candidates: list[dict],
                        text_key: str = "content") -> list[dict]:
        """关键字排序兜底（当 embedding 不可用时）"""
        tokens = set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", query.lower()))
        scored = []
        for c in candidates:
            text = (c.get(text_key, "") or "").lower()
            hits = sum(1 for t in tokens if t in text)
            scored.append((hits, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored if _ > 0] + [c for _, c in scored if _ == 0]
