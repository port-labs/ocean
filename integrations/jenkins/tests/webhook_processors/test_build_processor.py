import pytest
from unittest.mock import AsyncMock, patch
from typing import Any, Generator

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook.webhook_processors.build_webhook_processor import BuildWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from utils import ObjectKind
from webhook.events import BUILD_UPSERT_EVENTS, BUILD_DELETE_EVENTS


@pytest.fixture
def valid_build_payload() -> dict[str, Any]:
    return {
        "url": "http://jenkins/job/test/1",
        "id": "test-build-1",
        "type": "run.started",
        "source": "test",
    }


@pytest.fixture
def invalid_build_payload() -> dict[str, Any]:
    return {"id": "test-build-1", "type": "invalid"}


@pytest.fixture
def build_processor(mock_webhook_event: WebhookEvent) -> BuildWebhookProcessor:
    return BuildWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def mock_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.BUILD,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='.url | split("://")[1] | sub("^.*?/"; "") | gsub("%20"; "-") | gsub("%252F"; "-") | gsub("/"; "-") | .[:-1]',
                    title=".displayName",
                    blueprint='"jenkinsBuild"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook.webhook_processors.build_webhook_processor.JenkinsClient"
    ) as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestBuildWebhookProcessor:

    @pytest.mark.parametrize("type", BUILD_UPSERT_EVENTS + BUILD_DELETE_EVENTS)
    async def test_should_process_event_valid_payload(
        self,
        build_processor: BuildWebhookProcessor,
        valid_build_payload: dict[str, Any],
        type: str,
    ) -> None:
        valid_build_payload["type"] = type
        event = WebhookEvent(trace_id="test", payload=valid_build_payload, headers={})
        should_process = await build_processor.should_process_event(event)
        assert should_process is True

    async def test_should_process_event_invalid_payload(
        self,
        build_processor: BuildWebhookProcessor,
        invalid_build_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=invalid_build_payload, headers={})
        should_process = await build_processor.should_process_event(event)
        assert should_process is False

    async def test_handle_event_success(
        self,
        mock_client: AsyncMock,
        build_processor: BuildWebhookProcessor,
        valid_build_payload: dict[str, Any],
        mock_resource_config: ResourceConfig,
    ) -> None:

        mock_client.get_single_resource.return_value = valid_build_payload

        result = await build_processor.handle_event(
            valid_build_payload, mock_resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == valid_build_payload
        assert len(result.deleted_raw_results) == 0

        mock_client.get_single_resource.assert_called_once_with(
            "http://jenkins/job/test/1"
        )
