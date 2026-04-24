import pytest
from unittest.mock import MagicMock, patch
from typing import Any, AsyncGenerator
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_cloud.helpers.utils import ObjectKind
from bitbucket_cloud.webhook_processors.options import PullRequestSelectorOptions

# Patch the module before importing the class
with patch("initialize_client.init_webhook_client") as mock_init_client:
    from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient
    from bitbucket_cloud.webhook_processors.processors.pull_request_webhook_processor import (
        PullRequestWebhookProcessor,
    )


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def pull_request_webhook_processor(
    webhook_client_mock: BitbucketWebhookClient, event: WebhookEvent
) -> PullRequestWebhookProcessor:
    """Create a PullRequestWebhookProcessor with mocked webhook client."""
    pull_request_webhook_processor = PullRequestWebhookProcessor(event)
    pull_request_webhook_processor._webhook_client = webhook_client_mock
    return pull_request_webhook_processor


class TestPullRequestWebhookProcessor:

    @pytest.mark.parametrize(
        "event_key, expected",
        [
            ("pullrequest:created", True),
            ("pullrequest:updated", True),
            ("pullrequest:approved", True),
            ("pullrequest:unapproved", True),
            ("pullrequest:fulfilled", True),
            ("pullrequest:rejected", True),
            ("repo:created", False),
            ("repo:updated", False),
            ("repo:deleted", False),
            ("invalid:event", False),
        ],
    )
    @pytest.mark.asyncio
    async def test_should_process_event(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        event_key: str,
        expected: bool,
    ) -> None:
        """Test that should_process_event correctly identifies valid PR events."""
        event = WebhookEvent(
            trace_id="test-trace-id", headers={"x-event-key": event_key}, payload={}
        )
        result = await pull_request_webhook_processor._should_process_event(event)
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_matching_kinds(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        """Test that get_matching_kinds returns the PULL_REQUEST kind."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-event-key": "pullrequest:created"},
            payload={},
        )
        result = await pull_request_webhook_processor.get_matching_kinds(event)
        assert result == [ObjectKind.PULL_REQUEST]

    @pytest.mark.asyncio
    async def test_handle_event(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        webhook_client_mock: MagicMock,
    ) -> None:
        """Test handling a pull request event."""
        # Arrange
        payload = {
            "repository": {"uuid": "repo-123", "name": "test-repo"},
            "pullrequest": {"id": "pr-456", "state": "OPEN"},
        }
        resource_config = MagicMock()
        resource_config.selector.states = ["OPEN"]
        resource_config.selector.user_role = None
        resource_config.selector.repo_query = None

        webhook_client_mock.get_pull_request.return_value = {
            "id": "pr-456",
            "title": "Test PR",
            "description": "This is a test pull request",
            "state": "OPEN",
        }

        # Act
        result = await pull_request_webhook_processor.handle_event(
            payload, resource_config
        )

        # Assert
        webhook_client_mock.get_pull_request.assert_called_once_with(
            "repo-123", "pr-456"
        )
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {
            "id": "pr-456",
            "title": "Test PR",
            "description": "This is a test pull request",
            "state": "OPEN",
        }
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.parametrize(
        "payload, expected",
        [
            ({"repository": {}, "pullrequest": {}}, True),
            ({"repository": {}}, False),
            ({"pullrequest": {}}, False),
            ({}, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_validate_payload(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        payload: dict[str, Any],
        expected: bool,
    ) -> None:
        """Test payload validation with various input scenarios."""
        result = await pull_request_webhook_processor.validate_payload(payload)
        assert result == expected

    @pytest.mark.parametrize(
        "options, repo_exists, expected",
        [
            # Case 1: No filters set -> Should pass
            ({"user_role": None, "repo_query": None}, False, True),
            # Case 2: Filters set, repository matches -> Should pass
            ({"user_role": "admin", "repo_query": "name~test"}, True, True),
            # Case 3: Filters set, repository does not match -> Should fail
            ({"user_role": "admin", "repo_query": "name~test"}, False, False),
            # Case 4: Filters set, repository does not match -> Should fail
            ({"user_role": None, "repo_query": "name~test"}, False, False),
            # Case 5: Filters set, repository matches -> Should pass
            ({"user_role": None, "repo_query": "name~test"}, True, True),
        ],
    )
    @pytest.mark.asyncio
    async def test_check_repository_filter(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        webhook_client_mock: MagicMock,
        options: PullRequestSelectorOptions,
        repo_exists: bool,
        expected: bool,
    ) -> None:
        """Test _check_repository_filter with various scenarios."""

        async def mock_repositories_generator(
            params: dict[str, Any]
        ) -> AsyncGenerator[dict[str, Any], None]:
            if repo_exists:
                yield {"uuid": "repo-uuid"}

        webhook_client_mock.get_repositories.side_effect = mock_repositories_generator

        result = await pull_request_webhook_processor._check_repository_filter(
            "repo-uuid", options
        )
        assert result == expected
        if options["user_role"] or options["repo_query"]:
            webhook_client_mock.get_repositories.assert_called()
