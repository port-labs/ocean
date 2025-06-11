from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from github.core.options import SingleReleaseOptions

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.RELEASE,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    title=".name",
                    blueprint='"release"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def release_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> ReleaseWebhookProcessor:
    return ReleaseWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestReleaseWebhookProcessor:

    @pytest.mark.parametrize(
        "github_event,result", [(ObjectKind.RELEASE, True), ("invalid", False)]
    )
    async def test_should_process_event(
        self,
        release_webhook_processor: ReleaseWebhookProcessor,
        github_event: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert await release_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, release_webhook_processor: ReleaseWebhookProcessor
    ) -> None:
        kinds = await release_webhook_processor.get_matching_kinds(
            release_webhook_processor.event
        )
        assert ObjectKind.RELEASE in kinds

    @pytest.mark.parametrize(
        "action,is_deletion,expected_updated,expected_deleted",
        [
            ("created", False, True, False),
            ("deleted", True, False, True),
        ],
    )
    async def test_handle_event_create_and_delete(
        self,
        release_webhook_processor: ReleaseWebhookProcessor,
        resource_config: ResourceConfig,
        action: str,
        is_deletion: bool,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        release_data = {
            "id": 1,
            "name": "Release 1.0",
            "tag_name": "v1.0",
            "body": "Test release",
            "author": {"login": "user1"},
            "created_at": "2024-01-01T00:00:00Z",
        }

        payload = {
            "action": action,
            "release": release_data,
            "repository": {"name": "test-repo"},
        }

        if is_deletion:
            result = await release_webhook_processor.handle_event(
                payload, resource_config
            )
        else:
            # Mock the ReleaseExporter
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = release_data

            with patch(
                "github.webhook.webhook_processors.release_webhook_processor.RestReleaseExporter",
                return_value=mock_exporter,
            ):
                result = await release_webhook_processor.handle_event(
                    payload, resource_config
                )

            # Verify exporter was called with correct options
            mock_exporter.get_resource.assert_called_once_with(
                SingleReleaseOptions(repo_name="test-repo", release_id=1)
            )

        assert isinstance(result, WebhookEventRawResults)
        assert bool(result.updated_raw_results) is expected_updated
        assert bool(result.deleted_raw_results) is expected_deleted

        if expected_updated:
            assert result.updated_raw_results == [release_data]

        if expected_deleted:
            assert result.deleted_raw_results == [release_data]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"release": {"id": 1, "name": "Release 1.0"}}, True),
            ({"action": "unknown_event"}, False),  # missing release
            ({"release": {}}, False),  # missing id
        ],
    )
    async def test_validate_payload(
        self,
        release_webhook_processor: ReleaseWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await release_webhook_processor._validate_payload(payload)
        assert result is expected
