from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.helpers.invoke_completion import (
    register_catalog_response_from_body,
    response_body_for_catalog,
)
from azure_integration.foundry.helpers.scope import project_endpoint_context

_ENDPOINT = "https://acct.services.ai.azure.com/api/projects/demo"


@pytest.mark.asyncio
async def test_response_body_for_catalog_fetches_when_usage_missing() -> None:
    with patch(
        "azure_integration.foundry.helpers.invoke_completion.fetch_foundry_response",
        AsyncMock(return_value={"id": "resp_1", "usage": {"input_tokens": 1}}),
    ) as fetch:
        body = await response_body_for_catalog("resp_1", {"id": "resp_1"})
    fetch.assert_awaited_once_with("resp_1")
    assert body == {"id": "resp_1", "usage": {"input_tokens": 1}}


@pytest.mark.asyncio
async def test_register_applies_model_deployment_fallback() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock()
    mock_ocean.register_raw = AsyncMock()
    mock_ocean.port_client.post_run_log = AsyncMock()
    run = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=None)
    ctx.__aexit__ = AsyncMock(return_value=None)
    with (
        project_endpoint_context(_ENDPOINT, project_arm_id="arm-project"),
        patch("azure_integration.foundry.helpers.catalog_sync.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.catalog_sync.event_context",
            return_value=ctx,
        ),
    ):
        ok = await register_catalog_response_from_body(
            {"id": "resp_1", "status": "completed"},
            run,
            fallback_model_deployment_id="gpt-4o-mini",
        )
    assert ok is True
    assert mock_ocean.register_raw.await_args is not None
    batch = mock_ocean.register_raw.await_args.args[1]
    assert batch[0]["model_deployment_id"] == "gpt-4o-mini"
