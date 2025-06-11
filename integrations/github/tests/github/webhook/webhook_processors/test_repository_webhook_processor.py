from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.events import REPOSITORY_UPSERT_EVENTS, REPOSITORY_DELETE_EVENTS
from github.core.options import SingleRepositoryOptions

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
        kind=ObjectKind.REPOSITORY,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".full_name",
                    title=".name",
                    blueprint='"githubRepository"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def repository_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> RepositoryWebhookProcessor:
    return RepositoryWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestRepositoryWebhookProcessor:

    @pytest.mark.parametrize(
        "github_event,result", [(ObjectKind.REPOSITORY, True), ("invalid", False)]
    )
    async def test_should_process_event(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
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

        assert await repository_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        kinds = await repository_webhook_processor.get_matching_kinds(
            repository_webhook_processor.event
        )
        assert ObjectKind.REPOSITORY in kinds

    @pytest.mark.parametrize(
        "action,is_deletion,expected_updated,expected_deleted",
        [
            ("created", False, True, False),
            ("deleted", True, False, True),
        ],
    )
    async def test_handle_event_create_and_delete(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        resource_config: ResourceConfig,
        action: str,
        is_deletion: bool,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        repo_data = {
            "id": 1,
            "name": "test-repo",
            "full_name": "test-org/test-repo",
            "description": "Test repository",
        }

        payload = {"action": action, "repository": repo_data}

        if is_deletion:
            result = await repository_webhook_processor.handle_event(
                payload, resource_config
            )
        else:
            # Mock the RepositoryExporter
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = repo_data

            with patch(
                "github.webhook.webhook_processors.repository_webhook_processor.RestRepositoryExporter",
                return_value=mock_exporter,
            ):
                result = await repository_webhook_processor.handle_event(
                    payload, resource_config
                )

            # Verify exporter was called with correct repo name
            mock_exporter.get_resource.assert_called_once_with(
                SingleRepositoryOptions(name="test-repo")
            )

        assert isinstance(result, WebhookEventRawResults)
        assert bool(result.updated_raw_results) is expected_updated
        assert bool(result.deleted_raw_results) is expected_deleted

        if expected_updated:
            assert result.updated_raw_results == [repo_data]

        if expected_deleted:
            assert result.deleted_raw_results == [repo_data]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "action": REPOSITORY_UPSERT_EVENTS[0],
                    "repository": {"name": "repo1"},
                },
                True,
            ),
            (
                {
                    "action": REPOSITORY_DELETE_EVENTS[0],
                    "repository": {"name": "repo2"},
                },
                True,
            ),
            ({"action": "unknown_event", "repository": {"name": "repo3"}}, False),
            ({"repository": {"name": "repo4"}}, False),  # missing action
        ],
    )
    async def test_validate_payload(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await repository_webhook_processor._validate_payload(payload)
        assert result is expected
