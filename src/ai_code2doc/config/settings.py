from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AI_CODE2DOC_",
        env_file=".env",
        env_file_encoding="utf-8",
        toml_file="ai_code2doc.toml",
    )

    # LLM settings
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.1
    llm_concurrency: int = 3

    # Analysis settings
    max_file_size_kb: int = 500
    chunk_size_tokens: int = 3000
    output_dir: str = ".ai_code2doc"

    # Vector store
    chroma_persist_dir: str = ".ai_code2doc/chroma"
    embedding_model: str = "text-embedding-3-small"

    # Web
    web_host: str = "0.0.0.0"
    web_port: int = 8420

    # General
    log_level: str = "INFO"
