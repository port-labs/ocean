from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.helpers.invoke_completion import (
    response_body_for_catalog,
    register_catalog_response_from_body,
)


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
    run = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=None)
    ctx.__aexit__ = AsyncMock(return_value=None)
    with (
        patch("azure_integration.foundry.helpers.catalog_sync.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.catalog_sync.enrich_with_project",
            side_effect=lambda x: x,
        ),
        patch(
            "azure_integration.foundry.helpers.catalog_sync.normalize_catalog_payload",
            side_effect=lambda _kind, row: row,
        ),
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
