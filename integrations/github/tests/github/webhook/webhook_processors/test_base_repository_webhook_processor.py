from typing import Any, Dict
from unittest.mock import AsyncMock, patch
from port_ocean.context.event import event_context
import pytest
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from github.helpers.models import RepoSearchParams
from integration import GithubPortAppConfig, RepoSearchSelector
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults


class MockBaseRepositoryProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test_kind"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


@pytest.fixture
def base_repository_processor(
    mock_webhook_event: WebhookEvent,
) -> MockBaseRepositoryProcessor:
    return MockBaseRepositoryProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestBaseRepositoryWebhookProcessor:
    @pytest.mark.parametrize(
        "payload,visibility_filter,expected",
        [
            # Test with missing repository
            ({}, "all", False),
            # Test with missing repository name
            ({"repository": {}, "organization": {"login": "test-org"}}, "all", False),
            # Test with valid repository and "all" visibility
            (
                {
                    "repository": {
                        "name": "test-repo",
                        "visibility": "public",
                        "default_branch": "main",
                    },
                    "organization": {"login": "test-org"},
                },
                "all",
                True,
            ),
            # Test with matching visibility
            (
                {
                    "repository": {"name": "test-repo", "visibility": "private"},
                    "organization": {"login": "test-org"},
                },
                "private",
                True,
            ),
            # Test with non-matching visibility
            (
                {
                    "repository": {"name": "test-repo", "visibility": "public"},
                    "organization": {"login": "test-org"},
                },
                "private",
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        base_repository_processor: MockBaseRepositoryProcessor,
        payload: Dict[str, Any],
        visibility_filter: str,
        expected: bool,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        # Mock the port_app_config
        mock_port_app_config.repository_type = visibility_filter

        async with event_context("test_event") as event:
            event.port_app_config = mock_port_app_config
            result = await base_repository_processor.validate_payload(payload)
            assert result is expected

    @staticmethod
    def _resource_config(selector: RepoSearchSelector) -> ResourceConfig:
        return ResourceConfig(
            kind="test_kind",
            selector=selector,
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"testBlueprint"',
                        properties={},
                    )
                )
            ),
        )

    @pytest.mark.parametrize(
        "exclude_archived,archived,expected",
        [
            # exclude_archived enabled and repo is archived -> blocked
            (True, True, False),
            # exclude_archived enabled but repo is not archived -> allowed
            (True, False, True),
            # exclude_archived disabled (default) even though repo is archived -> unaffected
            (False, True, True),
            (False, False, True),
        ],
    )
    async def test_should_process_repo_search_excludes_archived(
        self,
        base_repository_processor: MockBaseRepositoryProcessor,
        exclude_archived: bool,
        archived: bool,
        expected: bool,
    ) -> None:
        payload: Dict[str, Any] = {
            "repository": {"name": "test-repo", "archived": archived},
            "organization": {"login": "test-org"},
        }
        config = self._resource_config(
            RepoSearchSelector(query="true", excludeArchived=exclude_archived)
        )

        result = await base_repository_processor.should_process_repo_search(
            payload, config
        )
        assert result is expected

    async def test_should_process_repo_search_skips_search_api_when_archived_excluded(
        self,
        base_repository_processor: MockBaseRepositoryProcessor,
    ) -> None:
        """When exclude_archived already blocks the event, the (costlier)
        search-API based repo_search check should not run at all."""
        payload: Dict[str, Any] = {
            "repository": {"name": "test-repo", "archived": True},
            "organization": {"login": "test-org"},
        }
        config = self._resource_config(
            RepoSearchSelector(
                query="true",
                excludeArchived=True,
                repoSearch=RepoSearchParams(query="org:test-org"),
            )
        )

        with patch.object(
            base_repository_processor, "repo_in_search", new=AsyncMock()
        ) as mock_repo_in_search:
            result = await base_repository_processor.should_process_repo_search(
                payload, config
            )

        assert result is False
        mock_repo_in_search.assert_not_called()

    async def test_should_process_repo_search_still_applies_when_not_archived(
        self,
        base_repository_processor: MockBaseRepositoryProcessor,
    ) -> None:
        """exclude_archived only short-circuits for archived repos - the
        existing repo_search matching still runs normally otherwise."""
        payload: Dict[str, Any] = {
            "repository": {"name": "test-repo", "archived": False},
            "organization": {"login": "test-org"},
        }
        config = self._resource_config(
            RepoSearchSelector(
                query="true",
                excludeArchived=True,
                repoSearch=RepoSearchParams(query="org:test-org"),
            )
        )

        with patch.object(
            base_repository_processor,
            "repo_in_search",
            new=AsyncMock(return_value=None),
        ) as mock_repo_in_search:
            result = await base_repository_processor.should_process_repo_search(
                payload, config
            )

        assert result is False
        mock_repo_in_search.assert_called_once_with(payload, config)
