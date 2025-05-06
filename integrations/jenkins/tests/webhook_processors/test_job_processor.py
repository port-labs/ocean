import pytest
from unittest.mock import AsyncMock, patch
from typing import Any, Generator

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook.webhook_processors.job_webhook_processor import JobWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from utils import ObjectKind
from webhook.events import JOB_UPSERT_EVENTS, JOB_DELETE_EVENTS


@pytest.fixture
def valid_job_payload() -> dict[str, Any]:
    return {"url": "http://jenkins/job/test", "id": "test-job", "type": "item.created"}


@pytest.fixture
def invalid_job_payload() -> dict[str, Any]:
    return {"id": "test-job", "type": "invalid"}


@pytest.fixture
def job_processor(mock_webhook_event: WebhookEvent) -> JobWebhookProcessor:
    return JobWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def mock_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.JOB,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='.url | split("://")[1] | sub("^.*?/"; "") | gsub("%20"; "-") | gsub("%252F"; "-") | gsub("/"; "-") | .[:-1]',
                    title=".fullName",
                    blueprint='"jenkinsJob"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook.webhook_processors.job_webhook_processor.JenkinsClient"
    ) as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestJobWebhookProcessor:

    @pytest.mark.parametrize("type", JOB_UPSERT_EVENTS + JOB_DELETE_EVENTS)
    async def test_should_process_event_valid_payload(
        self,
        job_processor: JobWebhookProcessor,
        valid_job_payload: dict[str, Any],
        type: str,
    ) -> None:
        valid_job_payload["type"] = type
        event = WebhookEvent(trace_id="test", payload=valid_job_payload, headers={})
        should_process = await job_processor.should_process_event(event)
        assert should_process is True

    async def test_should_process_event_invalid_payload(
        self, job_processor: JobWebhookProcessor, invalid_job_payload: dict[str, Any]
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=invalid_job_payload, headers={})
        should_process = await job_processor.should_process_event(event)
        assert should_process is False

    async def test_handle_event_success(
        self,
        mock_client: AsyncMock,
        job_processor: JobWebhookProcessor,
        valid_job_payload: dict[str, Any],
        mock_resource_config: ResourceConfig,
    ) -> None:

        mock_client.get_single_resource.return_value = valid_job_payload

        result = await job_processor.handle_event(
            valid_job_payload, mock_resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == valid_job_payload
        assert len(result.deleted_raw_results) == 0

        mock_client.get_single_resource.assert_called_once_with(
            "http://jenkins/job/test"
        )
