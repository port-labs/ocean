from typing import Literal
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)

from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from github.webhook.events import PULL_REQUEST_EVENTS
from github.core.options import SinglePullRequestOptions
from integration import GithubPullRequestSelector, GithubPullRequestConfig


@pytest.fixture
def pull_request_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> PullRequestWebhookProcessor:
    return PullRequestWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def resource_config() -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind=ObjectKind.PULL_REQUEST,
        selector=GithubPullRequestSelector(
            query="true",
            states=["open"],
            api="rest",
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".head.repo.name + (.id|tostring)",
                    title=".title",
                    blueprint='"githubPullRequest"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestPullRequestWebhookProcessor:
    async def test_should_process_event_valid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "pull_request"}
        mock_event.payload = {"action": "opened"}

        assert (
            await pull_request_webhook_processor._should_process_event(mock_event)
            is True
        )

    async def test_should_process_event_invalid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "some_other_event"}

        assert (
            await pull_request_webhook_processor._should_process_event(mock_event)
            is False
        )

    async def test_get_matching_kinds(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await pull_request_webhook_processor.get_matching_kinds(mock_event)
        assert kinds == [ObjectKind.PULL_REQUEST]

    async def test_validate_payload_valid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:

        # Valid upsert payload
        for action in PULL_REQUEST_EVENTS:
            payload = {
                "action": action,
                "pull_request": {"number": 101},
                "repository": {"name": "test-repo"},
            }
            assert (
                await pull_request_webhook_processor._validate_payload(payload) is True
            )

    async def test_validate_payload_invalid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:

        # Missing pull_request
        payload = {"action": "opened", "repository": {"name": "test-repo"}}
        assert await pull_request_webhook_processor._validate_payload(payload) is False

        # Missing pull request number
        payload = {
            "action": "opened",
            "pull_request": {},
            "repository": {"name": "test-repo"},
        }
        assert await pull_request_webhook_processor._validate_payload(payload) is False

    @pytest.mark.parametrize(
        "selector_states,action,expected_update,expected_delete",
        [
            (["open"], "opened", True, False),  # open allowed
            (["open"], "closed", False, True),  # closed not in states → delete
            (
                ["closed"],
                "opened",
                False,
                True,
            ),  # open state excluded by states → delete
            (["closed"], "closed", True, False),  # closed allowed → update
            (["open", "closed"], "closed", True, False),  # both allowed → update
        ],
    )
    async def test_handle_event_with_selector_states(
        self,
        selector_states: list[Literal["open", "closed"]],
        action: str,
        expected_update: bool,
        expected_delete: bool,
        resource_config: GithubPullRequestConfig,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
    ) -> None:
        resource_config.selector.states = selector_states

        pr_data = {
            "id": 1,
            "number": 101,
            "title": "Test PR",
            "state": "open" if action == "opened" else "closed",
        }
        repo_data = {"name": "test-repo", "full_name": "test-org/test-repo"}
        payload = {
            "action": action,
            "pull_request": pr_data,
            "repository": repo_data,
            "organization": {"login": "test-org"},
        }

        updated_pr_data = {**pr_data, "additional_data": "from_api"}
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = updated_pr_data

        with patch(
            "github.webhook.webhook_processors.base_pull_request_webhook_processor.RestPullRequestExporter",
            return_value=mock_exporter,
        ):
            result = await pull_request_webhook_processor.handle_event(
                payload, resource_config
            )

            assert isinstance(result, WebhookEventRawResults)

            if expected_update:
                assert result.updated_raw_results == [updated_pr_data]
                assert result.deleted_raw_results == []
                mock_exporter.get_resource.assert_called_once_with(
                    SinglePullRequestOptions(
                        organization="test-org",
                        repo_name="test-repo",
                        pr_number=101,
                        repo=None,
                        enrich_with_first_commit=False,
                        exclude_graphql_fields=[],
                    )
                )
            elif expected_delete:
                assert result.updated_raw_results == []
                if action == "closed":
                    # Early delete path uses payload PR data enriched with metadata
                    assert result.deleted_raw_results == [
                        {**pr_data, "__organization": "test-org"}
                    ]
                    mock_exporter.get_resource.assert_not_called()
                else:
                    # Post-fetch delete: fetched state excluded by selector
                    assert result.deleted_raw_results == [updated_pr_data]
                    mock_exporter.get_resource.assert_called_once()

    async def test_handle_event_passes_excluded_graphql_fields_when_configured(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        resource_config: GithubPullRequestConfig,
    ) -> None:
        resource_config.selector.api = "graphql"
        resource_config.selector.exclude_graphql_fields = ["additions", "changedFiles"]

        pr_data = {"id": 1, "number": 101, "title": "Test PR", "state": "open"}
        repo_data = {"name": "test-repo", "full_name": "test-org/test-repo"}
        payload = {
            "action": "opened",
            "pull_request": pr_data,
            "repository": repo_data,
            "organization": {"login": "test-org"},
        }

        updated_pr_data = {**pr_data, "additional_data": "from_api"}
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = updated_pr_data

        with patch(
            "github.webhook.webhook_processors.base_pull_request_webhook_processor.GraphQLPullRequestExporter",
            return_value=mock_exporter,
        ):
            result = await pull_request_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [updated_pr_data]
        mock_exporter.get_resource.assert_called_once()
        called_opts = mock_exporter.get_resource.call_args.args[0]
        assert called_opts["exclude_graphql_fields"] == ["additions", "changedFiles"]

    @pytest.mark.parametrize(
        "api,selector_states,pr_state_from_api,expected_update",
        [
            # GraphQL: "merged" state should be treated as "closed" when checking selector
            # When 'closed' is in states, merged PRs should be kept (upserted)
            ("graphql", ["open", "closed"], "merged", True),
            ("graphql", ["closed"], "merged", True),
            # GraphQL: "closed" state (not merged) should work as before
            ("graphql", ["open", "closed"], "closed", True),
            ("graphql", ["closed"], "closed", True),
            # REST: "closed" state (REST returns "closed" for merged PRs)
            ("rest", ["open", "closed"], "closed", True),
            ("rest", ["closed"], "closed", True),
        ],
    )
    async def test_handle_event_merged_pr_state_upserted_when_closed_in_states(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        resource_config: GithubPullRequestConfig,
        api: Literal["rest", "graphql"],
        selector_states: list[Literal["open", "closed"]],
        pr_state_from_api: str,
        expected_update: bool,
    ) -> None:
        """Test that merged PRs (state='merged' from GraphQL) are kept when 'closed' is in selector states.

        The GraphQL API returns state='MERGED' for merged PRs, which gets normalized to 'merged'.
        The REST API returns state='closed' for merged PRs.
        When the selector includes 'closed', merged PRs should be kept (upserted), not deleted.
        This test covers the case where the exporter is called and returns the PR data.
        """
        resource_config.selector.api = api
        resource_config.selector.states = selector_states

        pr_data = {"id": 1, "number": 101, "title": "Test PR", "state": "closed"}
        repo_data = {"name": "test-repo", "full_name": "test-org/test-repo"}
        payload = {
            "action": "closed",
            "pull_request": pr_data,
            "repository": repo_data,
            "organization": {"login": "test-org"},
        }

        fetched_pr_data = {
            **pr_data,
            "state": pr_state_from_api,
            "additional_data": "from_api",
        }
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = fetched_pr_data

        exporter_path = (
            "github.webhook.webhook_processors.base_pull_request_webhook_processor.GraphQLPullRequestExporter"
            if api == "graphql"
            else "github.webhook.webhook_processors.base_pull_request_webhook_processor.RestPullRequestExporter"
        )

        with patch(exporter_path, return_value=mock_exporter):
            result = await pull_request_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [fetched_pr_data]
        assert result.deleted_raw_results == []
        mock_exporter.get_resource.assert_called_once()

    @pytest.mark.parametrize(
        "api,pr_state_from_api",
        [
            # GraphQL: "merged" state should be deleted when 'closed' is NOT in states
            ("graphql", "merged"),
            # GraphQL: "closed" state should be deleted when 'closed' is NOT in states
            ("graphql", "closed"),
            # REST: "closed" state should be deleted when 'closed' is NOT in states
            ("rest", "closed"),
        ],
    )
    async def test_handle_event_merged_pr_deleted_when_closed_not_in_states(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        resource_config: GithubPullRequestConfig,
        api: Literal["rest", "graphql"],
        pr_state_from_api: str,
    ) -> None:
        """Test that merged/closed PRs are deleted when 'closed' is NOT in selector states.

        When the selector only includes 'open', a closed/merged PR should be deleted.
        This hits the early delete path (before calling the exporter) because
        action='closed' and 'closed' is not in states.
        """
        resource_config.selector.api = api
        resource_config.selector.states = ["open"]

        pr_data = {"id": 1, "number": 101, "title": "Test PR", "state": "closed"}
        repo_data = {"name": "test-repo", "full_name": "test-org/test-repo"}
        payload = {
            "action": "closed",
            "pull_request": pr_data,
            "repository": repo_data,
            "organization": {"login": "test-org"},
        }

        mock_exporter = AsyncMock()

        exporter_path = (
            "github.webhook.webhook_processors.base_pull_request_webhook_processor.GraphQLPullRequestExporter"
            if api == "graphql"
            else "github.webhook.webhook_processors.base_pull_request_webhook_processor.RestPullRequestExporter"
        )

        with patch(exporter_path, return_value=mock_exporter):
            result = await pull_request_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        # Early delete path uses enriched payload PR data (not fetched data)
        assert result.deleted_raw_results == [{**pr_data, "__organization": "test-org"}]
        # Exporter should NOT be called in early delete path
        mock_exporter.get_resource.assert_not_called()
