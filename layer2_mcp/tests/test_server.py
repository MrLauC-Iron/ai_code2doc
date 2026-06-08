"""Tests for HTTP server endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from code2doc_layer2_mcp.config import Layer2Settings
from code2doc_layer2_mcp.server import create_app


@pytest.fixture
def modules_dir(tmp_path: Path) -> Path:
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "auth.md").write_text("# Module: auth\n\nAuth docs.\n", encoding="utf-8")
    (modules / "user.md").write_text("# Module: user\n\nUser docs.\n", encoding="utf-8")
    return modules


@pytest.fixture
def settings(modules_dir: Path) -> Layer2Settings:
    return Layer2Settings(
        llm_api_key="test-key",
        modules_dir=str(modules_dir),
    )


@pytest.fixture
def app(settings: Layer2Settings):
    return create_app(settings)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestListModules:
    @pytest.mark.asyncio
    async def test_list_all(self, client: AsyncClient) -> None:
        resp = await client.get("/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modules"]) == 2
        names = [m["name"] for m in data["modules"]]
        assert "auth" in names
        assert "user" in names


class TestGetModule:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient) -> None:
        resp = await client.get("/modules/auth")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "auth"
        assert "# Module: auth" in data["content"]

    @pytest.mark.asyncio
    async def test_get_missing(self, client: AsyncClient) -> None:
        resp = await client.get("/modules/nonexistent")
        assert resp.status_code == 404


class TestSearchModules:
    @pytest.mark.asyncio
    async def test_search_match(self, client: AsyncClient) -> None:
        resp = await client.get("/modules?query=auth")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modules"]) == 1
        assert data["modules"][0]["name"] == "auth"

    @pytest.mark.asyncio
    async def test_search_no_match(self, client: AsyncClient) -> None:
        resp = await client.get("/modules?query=database")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modules"]) == 0


class TestUpdateModule:
    @pytest.mark.asyncio
    async def test_update_success(self, settings: Layer2Settings, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="# Module: auth\n\nUpdated docs."))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        mock_async_client = AsyncMock()
        mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("code2doc_layer2_mcp.llm_client.AsyncOpenAI", return_value=mock_async_client):
            app = create_app(settings)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                payload = {
                    "modules": ["auth"],
                    "task_description": "Add OAuth2 support",
                    "background": "Need OAuth2 for third-party login",
                    "layer1_overview": "Project has auth module at src/api/auth",
                    "code_changes": [
                        {"file": "auth.py", "diff": "+def oauth_login()", "action": "modified"},
                    ],
                }
                resp = await ac.post("/update", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["updated"]) == 1
        assert "auth" in data["updated"]

    @pytest.mark.asyncio
    async def test_update_missing_modules(self, client: AsyncClient) -> None:
        payload = {
            "task_description": "Some task",
        }
        resp = await client.post("/update", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_no_api_key(self, client: AsyncClient) -> None:
        from code2doc_layer2_mcp.config import Layer2Settings

        settings_no_key = Layer2Settings(
            llm_api_key="",
            modules_dir="modules",
        )
        app_no_key = create_app(settings_no_key)
        transport = ASGITransport(app=app_no_key)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "modules": ["auth"],
                "task_description": "Some task",
            }
            resp = await ac.post("/update", json=payload)
        assert resp.status_code == 400
