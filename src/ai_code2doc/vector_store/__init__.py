from ai_code2doc.vector_store.schemas import DocumentChunk, SearchResponse, SearchResult

__all__ = [
    "DocumentChunk",
    "Embedder",
    "SearchResponse",
    "SearchResult",
    "VectorStore",
]


def __getattr__(name: str):
    if name == "VectorStore":
        from ai_code2doc.vector_store.store import VectorStore
        return VectorStore
    if name == "Embedder":
        from ai_code2doc.vector_store.embedder import Embedder
        return Embedder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
