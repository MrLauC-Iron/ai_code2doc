"""Configuration for layer2_mcp server."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Layer2Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LAYER2_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # LLM settings
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.1

    # Server settings
    modules_dir: str = "modules"
    host: str = "0.0.0.0"
    port: int = 8001
