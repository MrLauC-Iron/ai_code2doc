"""code_qa tool: RAG-powered Q&A over the vector store."""

from __future__ import annotations

import asyncio

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult

tool_definition = ToolDefinition(
    name="code_qa",
    description="Answer questions about the codebase using RAG.",
    parameters=[
        ToolParameter(name="question", type="string", description="The question to answer"),
        ToolParameter(name="n_results", type="integer", description="Number of search results", required=False),
        ToolParameter(name="layer", type="integer", description="Restrict to layer (1, 2, or 3)", required=False),
    ],
)


def execute(call: ToolCall, context) -> ToolResult:
    if not context.has_vector_store():
        return ToolResult(tool_call_id=call.id, content="Vector store not available. Run 'ai-code2doc analyze' first.", is_error=True)

    question = call.arguments.get("question", "")
    if not question:
        return ToolResult(tool_call_id=call.id, content="No question provided.", is_error=True)

    n_results = call.arguments.get("n_results", 5)
    layer = call.arguments.get("layer")

    try:
        from ai_code2doc.vector_store.store import VectorStore
        from ai_code2doc.vector_store.schemas import SearchResponse

        vs = VectorStore(context.settings, str(context.chroma_dir))
        response: SearchResponse = vs.search(question, n_results=int(n_results), layer=layer)

        if not response.results:
            return ToolResult(tool_call_id=call.id, content=f"No relevant results found for: {question}", is_error=False)

        context_parts = []
        for r in response.results:
            source = r.metadata.get("source_path", "unknown")
            context_parts.append(f"### Source: {source} (score: {r.score:.2f})\n{r.content}")
        context_text = "\n\n---\n\n".join(context_parts)

        if context.settings.llm_api_key:
            try:
                prompt = (
                    "You are a senior software architect answering questions about a codebase. "
                    "Use ONLY the context below to answer the question. "
                    "If the context does not contain enough information, say so clearly.\n\n"
                    f"## Context\n\n{context_text}\n\n"
                    f"## Question\n\n{question}\n\n"
                    "Provide a concise, well-structured answer in Markdown."
                )
                answer = asyncio.run(
                    context.llm_client.agenerate(prompt, system="You are a helpful code documentation assistant.")
                )
                return ToolResult(tool_call_id=call.id, content=answer.content)
            except Exception as exc:
                return ToolResult(tool_call_id=call.id, content=f"LLM generation failed: {exc}\n\nRaw results:\n{context_text}")
        else:
            return ToolResult(tool_call_id=call.id, content=context_text)

    except Exception as exc:
        return ToolResult(tool_call_id=call.id, content=f"Search failed: {exc}", is_error=True)