from __future__ import annotations

from ai_code2doc.config.settings import Settings
from ai_code2doc.models.knowledge import KnowledgeDocument
from ai_code2doc.vector_store.schemas import DocumentChunk, SearchResponse, SearchResult


class VectorStore:
    def __init__(self, settings: Settings | None = None, persist_dir: str | None = None):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self._settings = settings or Settings()
        persist_path = persist_dir or self._settings.chroma_persist_dir

        self._client = chromadb.PersistentClient(
            path=persist_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        from ai_code2doc.vector_store.embedder import Embedder
        self._embedder = Embedder(self._settings)
        self._collection = self._client.get_or_create_collection(
            name="code_knowledge",
            metadata={"description": "Code knowledge base for ai_code2doc"},
        )

    def add_documents(self, documents: list[KnowledgeDocument]) -> None:
        """Add knowledge documents to the vector store."""
        if not documents:
            return

        chunks = self._split_documents(documents)

        if not chunks:
            return

        ids = [c.id for c in chunks]
        texts = [c.content for c in chunks]
        metas = [c.metadata for c in chunks]

        # Generate embeddings
        embeddings = self._embedder.embed(texts)

        # Add to collection in batches
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self._collection.upsert(
                ids=ids[i:end],
                documents=texts[i:end],
                embeddings=embeddings[i:end],
                metadatas=metas[i:end],
            )

    def search(self, query: str, n_results: int = 5, layer: int | None = None) -> SearchResponse:
        """Search for relevant documents."""
        query_embedding = self._embedder.embed_single(query)

        where_filter = None
        if layer is not None:
            where_filter = {"layer": layer}

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0
                score = 1.0 - distance  # Convert distance to similarity
                search_results.append(SearchResult(
                    id=results["ids"][0][i],
                    content=doc or "",
                    score=score,
                    metadata=metadata,
                ))

        return SearchResponse(
            query=query,
            results=search_results,
            total=len(search_results),
        )

    def add_module_summaries(self, summaries: list[dict]) -> None:
        """Add module-level dependency summaries to a dedicated collection."""
        if not summaries:
            return
        collection = self._client.get_or_create_collection(
            name="dependency_modules",
            metadata={"description": "Module-level dependency summaries for Layer 3"},
        )
        ids = [s["id"] for s in summaries]
        texts = [s["content"] for s in summaries]
        metas = [s["metadata"] for s in summaries]
        embeddings = self._embedder.embed(texts)
        collection.delete(ids=ids)
        collection.upsert(
            ids=ids, documents=texts, embeddings=embeddings, metadatas=metas,
        )

    def search_modules(self, query: str, n_results: int = 5) -> list[dict]:
        """Search module dependency summaries by semantic similarity."""
        collection = self._client.get_or_create_collection(
            name="dependency_modules",
            metadata={"description": "Module-level dependency summaries for Layer 3"},
        )
        query_embedding = self._embedder.embed_single(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        items = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                items.append({
                    "content": doc or "",
                    "metadata": meta,
                    "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0.0),
                })
        return items

    def _split_documents(self, documents: list[KnowledgeDocument]) -> list[DocumentChunk]:
        """Split documents into chunks suitable for embedding."""
        chunks = []
        for doc in documents:
            # If document is short enough, use as-is
            if len(doc.content) <= 2000:
                chunks.append(DocumentChunk(
                    id=doc.id,
                    content=f"{doc.title}\n\n{doc.summary}\n\n{doc.content}",
                    metadata={
                        "layer": doc.layer,
                        "source_path": doc.source_path,
                        "title": doc.title,
                        "tags": ",".join(doc.tags),
                        "created_at": doc.created_at.isoformat(),
                    },
                ))
            else:
                # Split into paragraphs/sections
                sections = doc.content.split("\n## ")
                for i, section in enumerate(sections):
                    if not section.strip():
                        continue
                    chunk_content = section if i == 0 else "## " + section
                    chunks.append(DocumentChunk(
                        id=f"{doc.id}-chunk-{i}",
                        content=f"{doc.title}\n\n{chunk_content}",
                        metadata={
                            "layer": doc.layer,
                            "source_path": doc.source_path,
                            "title": doc.title,
                            "tags": ",".join(doc.tags),
                            "chunk_index": i,
                        },
                    ))
        return chunks

    def delete_all(self) -> None:
        """Clear all documents from the store."""
        self._client.delete_collection("code_knowledge")
        self._collection = self._client.get_or_create_collection(
            name="code_knowledge",
            metadata={"description": "Code knowledge base for ai_code2doc"},
        )

    def count(self) -> int:
        """Return number of documents in the store."""
        return self._collection.count()
