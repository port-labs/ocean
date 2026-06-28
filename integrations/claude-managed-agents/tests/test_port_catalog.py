from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.port_catalog import fetch_skill_content


@pytest.mark.asyncio
async def test_fetch_skill_content_calls_ai_service_endpoint() -> None:
    mock_ocean = MagicMock()
    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "skill": {
            "name": "my-skill",
            "title": "My Skill",
            "instructions": "# Skill",
            "resources": [{"path": "helpers/run.py", "content": "x = 1"}],
        }
    }
    mock_ocean.port_client.client.get = AsyncMock(return_value=mock_response)
    mock_ocean.port_client.auth.headers = AsyncMock(
        return_value={"Authorization": "Bearer t"}
    )
    mock_ocean.port_client.api_url = "https://api.getport.io/v1"

    with patch("clients.port_catalog.ocean", mock_ocean):
        result = await fetch_skill_content("my-skill")

    assert result["name"] == "my-skill"
    assert result["instructions"] == "# Skill"
    assert result["resources"][0]["path"] == "helpers/run.py"

    call = mock_ocean.port_client.client.get.await_args
    assert call.args[0].endswith("/skills/my-skill/content")


@pytest.mark.asyncio
async def test_fetch_skill_content_url_encodes_identifier() -> None:
    mock_ocean = MagicMock()
    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 200
    mock_response.json.return_value = {"skill": {"name": "s", "instructions": "# s"}}
    mock_ocean.port_client.client.get = AsyncMock(return_value=mock_response)
    mock_ocean.port_client.auth.headers = AsyncMock(
        return_value={"Authorization": "Bearer t"}
    )
    mock_ocean.port_client.api_url = "https://api.getport.io/v1"

    with patch("clients.port_catalog.ocean", mock_ocean):
        await fetch_skill_content("my skill/v1")

    call = mock_ocean.port_client.client.get.await_args
    assert "my+skill%2Fv1" in call.args[0]
