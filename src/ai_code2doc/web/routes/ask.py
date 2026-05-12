from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    n_context: int = 5


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict]


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: Request, body: AskRequest) -> AskResponse:
    """RAG-powered Q&A over the codebase."""
    root = _get_root(request)
    try:
        from ai_code2doc.config.settings import Settings

        settings = Settings()

        # Search for context
        from ai_code2doc.vector_store.store import VectorStore

        vs = VectorStore(settings, str(root / ".ai_code2doc" / "chroma"))
        search_result = vs.search(body.question, n_results=body.n_context)

        # Build context
        context_parts = []
        sources = []
        for r in search_result.results:
            context_parts.append(r.content)
            sources.append({"id": r.id, "score": r.score, "metadata": r.metadata})

        context = "\n\n---\n\n".join(context_parts)

        # Use LLM if available
        if settings.llm_api_key:
            from ai_code2doc.llm.client import LLMClient

            client = LLMClient(settings)

            prompt = f"""Based on the following code documentation, answer the question.

Documentation:
{context}

Question: {body.question}

Provide a detailed answer based on the documentation. If the documentation doesn't contain enough information, say so."""

            response = await client.agenerate(
                prompt,
                system="You are a helpful code documentation assistant.",
            )
            answer = response.content
        else:
            answer = (
                f"Found {len(sources)} relevant documents. "
                f"LLM not configured - showing raw context:\n\n{context[:2000]}"
            )

        return AskResponse(question=body.question, answer=answer, sources=sources)
    except Exception as e:
        return AskResponse(question=body.question, answer=f"Error: {e}", sources=[])


def _get_root(request: Request) -> Path:
    return request.app.state.project_root
