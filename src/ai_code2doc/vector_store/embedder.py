from __future__ import annotations

from openai import OpenAI

from ai_code2doc.config.settings import Settings


class Embedder:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._client = OpenAI(
            base_url=self._settings.llm_base_url,
            api_key=self._settings.llm_api_key or "dummy",
        )
        self._model = self._settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []
        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        result = self.embed([text])
        return result[0] if result else []
