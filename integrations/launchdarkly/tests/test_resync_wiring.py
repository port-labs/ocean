import pytest
from unittest.mock import AsyncMock, patch, PropertyMock
from typing import Any, Generator
from integration import FeatureFlagResourceConfig, FeatureFlagSelector
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)


@pytest.fixture
def mock_integration_config() -> Generator[dict[str, str], None, None]:
    """Mock the ocean integration config."""
    config = {
        "launchdarkly_host": "https://app.launchdarkly.com",
        "launchdarkly_token": "test_token",
        "webhook_secret": "test_secret",
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.mark.asyncio
async def test_on_resync_flags_wiring(
    mock_integration_config: dict[str, str],
) -> None:
    """Test that on_resync_flags reads selector from event and passes to client."""

    # Patch decorators before importing main
    with (
        patch("port_ocean.context.ocean.ocean.on_resync") as mock_on_resync,
        patch("port_ocean.context.ocean.ocean.on_start") as mock_on_start,
        patch(
            "port_ocean.context.ocean.ocean.add_webhook_processor"
        ) as mock_add_webhook,
    ):
        # Make decorators pass through
        mock_on_resync.side_effect = lambda **kwargs: lambda f: f
        mock_on_start.side_effect = lambda **kwargs: lambda f: f
        mock_add_webhook.side_effect = lambda *args: None

        # Import main module
        import importlib

        main = importlib.import_module("main")

        # Setup test data
        from client import ObjectKind

        resource_config = FeatureFlagResourceConfig(
            kind=ObjectKind.FEATURE_FLAG,
            selector=FeatureFlagSelector(
                query="true", summary=False, environments=["production", "staging"]
            ),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".key",
                        title=".name",
                        blueprint='"launchDarklyFeatureFlag"',
                        properties={},
                    )
                )
            ),
        )

        # Mock the client
        mock_client = AsyncMock()

        async def mock_get_paginated_flags(*args: Any, **kwargs: Any) -> Any:
            # Capture the call arguments
            mock_client.captured_summary = kwargs.get("summary")
            mock_client.captured_environments = kwargs.get("environments")
            yield [{"key": "flag-1", "__projectKey": "project-1"}]

        mock_client.get_paginated_feature_flags = mock_get_paginated_flags

        # Patch event and client
        mock_event = type("MockEvent", (), {"resource_config": resource_config})()

        with (
            patch("main.event", mock_event),
            patch.object(
                main.LaunchDarklyClient, "create_from_ocean_configuration"
            ) as mock_create,
        ):
            mock_create.return_value = mock_client

            # Call the resync function
            batches = []
            async for batch in main.on_resync_flags("flag"):
                batches.append(batch)

            # Verify results
            assert len(batches) == 1
            assert batches[0][0]["key"] == "flag-1"

            # Verify selector params were passed through
            assert mock_client.captured_summary is False
            assert mock_client.captured_environments == ["production", "staging"]
