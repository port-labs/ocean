from integration import GithubPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
import pytest
from unittest.mock import MagicMock, patch
from github.webhook.webhook_processors.collaborator_webhook_processor.membership_webhook_processor import (
    CollaboratorMembershipWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleTeamOptions
from typing import Any, AsyncGenerator
from port_ocean.context.event import event_context


VALID_MEMBERSHIP_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "action": "added",
    "repository": {"name": "test-repo"},
    "organization": {"login": "test-org"},
    "team": {"name": "test-team", "slug": "test-team"},
    "member": {"login": "test-user"},
}

INVALID_MEMBERSHIP_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "invalid": {
        "action": "invalid",
    },
    "missing_org": {
        "action": "added",
        "team": {"name": "test-team", "slug": "test-team"},
        "member": {"login": "test-user"},
    },
    "missing_team": {
        "action": "added",
        "organization": {"login": "test-org"},
        "member": {"login": "test-user"},
    },
    "missing_member": {
        "action": "added",
        "organization": {"login": "test-org"},
        "team": {"name": "test-team", "slug": "test-team"},
    },
    "missing_org_login": {
        "action": "added",
        "organization": {},
        "team": {"name": "test-team", "slug": "test-team"},
        "member": {"login": "test-user"},
    },
    "missing_team_name": {
        "action": "added",
        "organization": {"login": "test-org"},
        "team": {"slug": "test-team"},
        "member": {"login": "test-user"},
    },
    "missing_member_login": {
        "action": "added",
        "organization": {"login": "test-org"},
        "team": {"name": "test-team", "slug": "test-team"},
        "member": {},
    },
}


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.COLLABORATOR,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".login",
                    title=".login",
                    blueprint='"githubCollaborator"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def membership_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> CollaboratorMembershipWebhookProcessor:
    return CollaboratorMembershipWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestCollaboratorMembershipWebhookProcessor:
    @pytest.mark.parametrize(
        "event_type,action,expected",
        [
            ("membership", "added", True),
            ("membership", "edited", True),
            ("membership", "removed", True),
            ("member", "added", False),
            ("membership", "unknown_action", False),
            ("membership", None, False),
        ],
    )
    async def test_should_process_event(
        self,
        membership_webhook_processor: CollaboratorMembershipWebhookProcessor,
        event_type: str,
        action: str,
        expected: bool,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": event_type}
        mock_event.payload = {"action": action}

        assert (
            await membership_webhook_processor._should_process_event(mock_event)
            is expected
        )

    async def test_get_matching_kinds(
        self, membership_webhook_processor: CollaboratorMembershipWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        assert await membership_webhook_processor.get_matching_kinds(mock_event) == [
            ObjectKind.COLLABORATOR
        ]

    @pytest.mark.parametrize(
        "payload,expected_result",
        [
            (VALID_MEMBERSHIP_COLLABORATOR_PAYLOADS, True),
            (INVALID_MEMBERSHIP_COLLABORATOR_PAYLOADS["invalid"], False),
            (INVALID_MEMBERSHIP_COLLABORATOR_PAYLOADS["missing_org"], False),
            (INVALID_MEMBERSHIP_COLLABORATOR_PAYLOADS["missing_team"], False),
            (INVALID_MEMBERSHIP_COLLABORATOR_PAYLOADS["missing_member"], False),
            (INVALID_MEMBERSHIP_COLLABORATOR_PAYLOADS["missing_org_login"], False),
            (INVALID_MEMBERSHIP_COLLABORATOR_PAYLOADS["missing_team_name"], False),
            (INVALID_MEMBERSHIP_COLLABORATOR_PAYLOADS["missing_member_login"], False),
        ],
    )
    async def test_validate_payload(
        self,
        membership_webhook_processor: CollaboratorMembershipWebhookProcessor,
        payload: dict[str, Any],
        expected_result: bool,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        mock_port_app_config.repository_type = "all"

        async with event_context("test_event") as event_context_obj:
            event_context_obj.port_app_config = mock_port_app_config
            assert (
                await membership_webhook_processor.validate_payload(payload)
                is expected_result
            )

    @pytest.mark.parametrize(
        "action,expected_updated,expected_deleted",
        [
            ("added", True, False),
            ("edited", True, False),
            ("removed", False, False),  # Not in COLLABORATOR_UPSERT_EVENTS
            ("deleted", False, False),  # Not in COLLABORATOR_UPSERT_EVENTS
        ],
    )
    async def test_handle_event_membership_events(
        self,
        membership_webhook_processor: CollaboratorMembershipWebhookProcessor,
        resource_config: ResourceConfig,
        mock_port_app_config: GithubPortAppConfig,
        action: str,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        # Set up payload
        payload = VALID_MEMBERSHIP_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = action

        # Mock the repositories data
        mock_repositories = [
            {"name": "repo1", "full_name": "org/repo1", "visibility": "public"},
            {"name": "repo2", "full_name": "org/repo2", "visibility": "public"},
        ]

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.membership_webhook_processor.create_github_client"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            # Mock RestTeamExporter
            with patch(
                "github.webhook.webhook_processors.collaborator_webhook_processor.membership_webhook_processor.RestTeamExporter"
            ) as mock_team_exporter_class:
                mock_team_exporter = MagicMock()
                mock_team_exporter_class.return_value = mock_team_exporter

                # Mock the async generator for team repositories
                async def mock_get_team_repositories() -> (
                    AsyncGenerator[list[dict[str, Any]], None]
                ):
                    yield mock_repositories

                mock_team_exporter.get_team_repositories_by_slug.return_value = (
                    mock_get_team_repositories()
                )

                async with event_context("test_event") as event_context_obj:
                    event_context_obj.port_app_config = mock_port_app_config
                    result = await membership_webhook_processor.handle_event(
                        payload, resource_config
                    )

                # Verify the result
                assert isinstance(result, WebhookEventRawResults)
                assert bool(result.updated_raw_results) is expected_updated
                assert bool(result.deleted_raw_results) is expected_deleted

                if expected_updated:
                    # Verify enriched data structure
                    assert len(result.updated_raw_results) == len(mock_repositories)
                    for i, repo in enumerate(mock_repositories):
                        assert (
                            result.updated_raw_results[i]["__repository"]
                            == repo["name"]
                        )
                        assert result.updated_raw_results[i]["login"] == "test-user"

                    # Verify team exporter was called
                    mock_team_exporter.get_team_repositories_by_slug.assert_called_once_with(
                        SingleTeamOptions(organization="test-org", slug="test-team")
                    )
                else:
                    # For non-upsert events, no repositories should be fetched
                    mock_team_exporter.get_team_repositories_by_slug.assert_not_called()

    async def test_enrich_collaborators_with_repositories(
        self, membership_webhook_processor: CollaboratorMembershipWebhookProcessor
    ) -> None:
        """Test the helper method that enriches collaborators with repository information."""
        member_data = {"login": "test-user", "name": "Test User"}
        repositories = [
            {"name": "repo1", "full_name": "org/repo1"},
            {"name": "repo2", "full_name": "org/repo2"},
        ]

        result = membership_webhook_processor._enrich_collaborators_with_repositories(
            member_data, repositories
        )

        assert len(result) == 2
        assert result[0]["login"] == "test-user"
        assert result[0]["__repository"] == "repo1"
        assert result[1]["login"] == "test-user"
        assert result[1]["__repository"] == "repo2"
