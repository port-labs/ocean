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
from integration import GithubIssueSelector, GithubIssueConfig
from port_ocean.context.event import event_context

from github.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from github.webhook.events import ISSUE_EVENTS
from github.core.options import SingleIssueOptions


@pytest.fixture
def resource_config() -> GithubIssueConfig:
    return GithubIssueConfig(
        kind="issue",
        selector=GithubIssueSelector(query=".pull_request == null", state="open"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".repo + (.id|tostring)",
                    title=".title",
                    blueprint='"githubIssue"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def issue_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestIssueWebhookProcessor:
    async def test_should_process_event_valid(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "issues"}
        mock_event.payload = {"action": "opened"}

        assert await issue_webhook_processor._should_process_event(mock_event) is True

    async def test_should_process_event_invalid(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "some_other_event"}

        assert await issue_webhook_processor._should_process_event(mock_event) is False

    async def test_get_matching_kinds(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await issue_webhook_processor.get_matching_kinds(mock_event)
        assert kinds == [ObjectKind.ISSUE]

    async def test_validate_payload_valid(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        async with event_context("test_event"):
            # Valid payload for each issue action
            for action in ISSUE_EVENTS:
                payload = {
                    "action": action,
                    "issue": {"number": 101, "state": "open"},
                    "repository": {"name": "test-repo"},
                }
                assert await issue_webhook_processor._validate_payload(payload) is True

    async def test_validate_payload_invalid(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        async with event_context("test_event"):

            # Missing issue field
            payload = {"action": "opened", "repository": {"name": "test-repo"}}
            assert await issue_webhook_processor._validate_payload(payload) is False

            # Missing number in issue
            payload = {
                "action": "opened",
                "issue": {"state": "open"},
                "repository": {"name": "test-repo"},
            }
            assert await issue_webhook_processor._validate_payload(payload) is False

    @pytest.mark.parametrize(
        "action,issue_state,selector_state,expected_update,expected_delete",
        [
            ("opened", "open", "open", True, False),
            ("edited", "open", "open", True, False),
            ("closed", "closed", "open", False, True),
            ("closed", "closed", "closed", True, False),
            ("closed", "closed", "all", True, False),
            ("deleted", "open", "open", False, True),
            ("reopened", "open", "closed", True, False),
        ],
    )
    async def test_handle_event(
        self,
        action: str,
        issue_state: str,
        selector_state: Literal["open", "closed", "all"],
        expected_update: bool,
        expected_delete: bool,
        resource_config: GithubIssueConfig,
        issue_webhook_processor: IssueWebhookProcessor,
    ) -> None:
        # Setup issue data
        issue_data = {
            "id": 101,
            "number": 42,
            "title": "Test Issue",
            "state": issue_state,
        }

        repo_data = {"name": "test-repo"}

        # Setup payload
        payload = {"action": action, "issue": issue_data, "repository": repo_data}

        # Setup resource config
        resource_config.selector.state = selector_state

        # Create updated issue data from API
        updated_issue_data = {
            **issue_data,
            "body": "Issue description",
            "html_url": "https://github.com/org/repo/issues/42",
            "repository": {"name": "test-repo"},
        }

        # Mock the exporter
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = updated_issue_data

        with patch(
            "github.webhook.webhook_processors.issue_webhook_processor.RestIssueExporter",
            return_value=mock_exporter,
        ):
            result = await issue_webhook_processor.handle_event(
                payload, resource_config
            )

            # Verify the result
            assert isinstance(result, WebhookEventRawResults)

            if expected_update:
                assert result.updated_raw_results == [updated_issue_data]
                assert result.deleted_raw_results == []
                mock_exporter.get_resource.assert_called_once_with(
                    SingleIssueOptions(repo_name="test-repo", issue_number=42)
                )
            elif expected_delete:
                assert result.updated_raw_results == []
                assert result.deleted_raw_results == [issue_data]
                mock_exporter.get_resource.assert_not_called()
