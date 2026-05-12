from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    n_results: int = 5
    layer: int | None = None


class SearchResponseModel(BaseModel):
    query: str
    results: list[dict]


@router.post("/search", response_model=SearchResponseModel)
async def search_docs(request: Request, body: SearchRequest) -> SearchResponseModel:
    """Semantic search across the knowledge base."""
    root = _get_root(request)
    try:
        from ai_code2doc.vector_store.store import VectorStore
        from ai_code2doc.config.settings import Settings

        settings = Settings()
        vs = VectorStore(settings, str(root / ".ai_code2doc" / "chroma"))
        result = vs.search(body.query, n_results=body.n_results, layer=body.layer)
        return SearchResponseModel(
            query=result.query,
            results=[
                {
                    "id": r.id,
                    "content": r.content,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in result.results
            ],
        )
    except Exception as e:
        return SearchResponseModel(
            query=body.query,
            results=[{"id": "error", "content": str(e), "score": 0, "metadata": {}}],
        )


def _get_root(request: Request) -> Path:
    return request.app.state.project_root
