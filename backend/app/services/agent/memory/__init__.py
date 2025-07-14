"""智能体记忆子包 — MemoryManager + LocalEmbedder + Consolidator"""

from app.services.agent.memory.manager import MemoryManager
from app.services.agent.memory.embeddings import LocalEmbedder
from app.services.agent.memory.consolidator import (
    consolidate_memories,
    build_user_profile,
    MemoryProfile,
)

__all__ = [
    "MemoryManager",
    "LocalEmbedder",
    "consolidate_memories",
    "build_user_profile",
    "MemoryProfile",
]
