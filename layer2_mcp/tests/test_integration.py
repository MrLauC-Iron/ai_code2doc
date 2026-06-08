"""Integration tests: start server, exercise all endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from code2doc_layer2_mcp.config import Layer2Settings
from code2doc_layer2_mcp.server import create_app


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "auth.md").write_text("# Module: auth\n\nLogin and registration.", encoding="utf-8")
    (modules / "user.md").write_text("# Module: user\n\nUser profile management.", encoding="utf-8")
    return tmp_path


@pytest.fixture
def settings(project_dir: Path) -> Layer2Settings:
    return Layer2Settings(llm_api_key="test-key", modules_dir=str(project_dir / "modules"))


@pytest.fixture
async def client(settings: Layer2Settings):
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_full_workflow(client: AsyncClient, settings: Layer2Settings) -> None:
    """Test the complete workflow: list -> get -> search -> update -> verify."""

    # 1. List all modules
    resp = await client.get("/modules")
    assert resp.status_code == 200
    modules = resp.json()["modules"]
    assert len(modules) == 2

    # 2. Get specific module
    resp = await client.get("/modules/auth")
    assert resp.status_code == 200
    assert "Login" in resp.json()["content"]

    # 3. Search modules
    resp = await client.get("/modules?query=user")
    assert resp.status_code == 200
    assert len(resp.json()["modules"]) == 1
    assert resp.json()["modules"][0]["name"] == "user"

    # 4. Update a module via POST
    # The LLM client is created eagerly in create_app(), so we must create the
    # app INSIDE the patch context. We re-use the same settings (same modules_dir)
    # so the store writes to the same temp directory that the original client reads from.
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="# Module: auth\n\nUpdated: JWT login added."))]
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    mock_async_client = AsyncMock()
    mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("code2doc_layer2_mcp.llm_client.AsyncOpenAI", return_value=mock_async_client):
        app2 = create_app(settings)
        transport2 = ASGITransport(app=app2)
        async with AsyncClient(transport=transport2, base_url="http://test") as ac2:
            resp = await ac2.post("/update", json={
                "modules": ["auth"],
                "task_description": "Add JWT authentication",
                "background": "Replacing session-based auth",
                "layer1_overview": "Auth module at src/api/auth handles login/logout",
                "code_changes": [
                    {"file": "auth.py", "diff": "+def jwt_login(token)", "action": "modified"},
                ],
            })
    assert resp.status_code == 200
    assert "auth" in resp.json()["updated"]

    # 5. Verify the update via the original client -- the ModuleStore reads
    # from the same filesystem directory, so it picks up the saved changes.
    resp = await client.get("/modules/auth")
    assert resp.status_code == 200
    assert "JWT" in resp.json()["content"]
