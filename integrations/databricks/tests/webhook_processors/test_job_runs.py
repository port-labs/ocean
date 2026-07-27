from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from kinds import Kinds
from webhook_processors.job_runs import JobRunWebhookProcessor


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "workspace_url": "https://workspace.cloud.databricks.com",
            "token": "test-token",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://app.example.com"
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> JobRunWebhookProcessor:
    return JobRunWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def mock_client() -> Generator[MagicMock, None, None]:
    with patch("webhook_processors.job_runs.DatabricksClient") as mock:
        client = MagicMock()
        mock.from_ocean_configuration.return_value = client
        yield client


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=Kinds.JOB_RUNS,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".run_id | tostring",
                    title=".run_name",
                    blueprint='"databricksJobRun"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestJobRunWebhookProcessor:
    async def test_should_process_event_with_run_id(
        self, processor: JobRunWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="t1",
            payload={"event_type": "job_run_success", "run_id": 123},
            headers={},
        )
        assert await processor.should_process_event(event) is True

    async def test_should_process_event_without_run_id(
        self, processor: JobRunWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="t1", payload={"event_type": "job_run_success"}, headers={}
        )
        assert await processor.should_process_event(event) is False

    async def test_should_process_event_unknown_event_type(
        self, processor: JobRunWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="t1",
            payload={"event_type": "cluster_created", "run_id": 123},
            headers={},
        )
        assert await processor.should_process_event(event) is False

    async def test_should_process_event_nested_run_id(
        self, processor: JobRunWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="t1",
            payload={"event_details": {"run_id": 456}},
            headers={},
        )
        assert await processor.should_process_event(event) is True

    async def test_get_matching_kinds(self, processor: JobRunWebhookProcessor) -> None:
        event = WebhookEvent(trace_id="t1", payload={}, headers={})
        assert await processor.get_matching_kinds(event) == [Kinds.JOB_RUNS]

    async def test_validate_payload_true(
        self, processor: JobRunWebhookProcessor
    ) -> None:
        assert await processor.validate_payload({"run_id": 1}) is True

    async def test_validate_payload_false(
        self, processor: JobRunWebhookProcessor
    ) -> None:
        assert await processor.validate_payload({}) is False

    async def test_handle_event_fetches_and_returns_run(
        self,
        processor: JobRunWebhookProcessor,
        mock_client: MagicMock,
        resource_config: ResourceConfig,
    ) -> None:
        run_data = {"run_id": 123, "state": {"result_state": "SUCCESS"}}
        mock_client.get_job_run = AsyncMock(return_value=run_data)

        payload = {"event_type": "job_run_success", "run_id": 123}
        result = await processor.handle_event(payload, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [run_data]
        assert result.deleted_raw_results == []
        mock_client.get_job_run.assert_called_once_with("123")

    async def test_handle_event_missing_run_id_returns_empty(
        self,
        processor: JobRunWebhookProcessor,
        mock_client: MagicMock,
        resource_config: ResourceConfig,
    ) -> None:
        result = await processor.handle_event({}, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        mock_client.get_job_run.assert_not_called()
