from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.port_catalog import fetch_skill_content, set_port_skill_relation


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


@pytest.mark.asyncio
async def test_set_port_skill_relation_upserts_entity() -> None:
    mock_ocean = MagicMock()
    mock_config = MagicMock()
    mock_config.get_port_request_options.return_value = {"merge": True}
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock(
        return_value=mock_config
    )
    mock_ocean.port_client.upsert_entity = AsyncMock()

    with patch("clients.port_catalog.ocean", mock_ocean):
        await set_port_skill_relation("skill_new", "port-skill-1")

    mock_ocean.port_client.upsert_entity.assert_awaited_once()
    entity_arg = mock_ocean.port_client.upsert_entity.call_args.args[0]
    assert entity_arg.identifier == "skill_new"
    assert entity_arg.relations == {"portSkill": "port-skill-1"}


@pytest.mark.asyncio
async def test_set_port_skill_relation_is_best_effort() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock(
        side_effect=RuntimeError("boom")
    )

    with patch("clients.port_catalog.ocean", mock_ocean):
        await set_port_skill_relation("skill_new", "port-skill-1")
