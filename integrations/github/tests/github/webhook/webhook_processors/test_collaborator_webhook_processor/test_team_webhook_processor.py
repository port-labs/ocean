from integration import GithubPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor import (
    CollaboratorTeamWebhookProcessor,
)
from github.helpers.utils import ObjectKind, GithubClientType
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from typing import Any
from port_ocean.context.event import event_context


VALID_TEAM_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "action": "added_to_repository",
    "repository": {"name": "test-repo"},
    "organization": {"login": "test-org"},
    "team": {"name": "test-team", "slug": "test-team"},
}

INVALID_TEAM_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "invalid": {
        "action": "invalid",
    },
    "missing_repo": {
        "action": "added_to_repository",
        "organization": {"login": "test-org"},
        "team": {"name": "test-team", "slug": "test-team"},
    },
    "missing_org": {
        "action": "added_to_repository",
        "repository": {"name": "test-repo"},
        "team": {"name": "test-team", "slug": "test-team"},
    },
    "missing_team": {
        "action": "added_to_repository",
        "repository": {"name": "test-repo"},
        "organization": {"login": "test-org"},
    },
    "missing_org_login": {
        "action": "added_to_repository",
        "repository": {"name": "test-repo"},
        "organization": {},
        "team": {"name": "test-team", "slug": "test-team"},
    },
    "missing_team_name": {
        "action": "added_to_repository",
        "repository": {"name": "test-repo"},
        "organization": {"login": "test-org"},
        "team": {"slug": "test-team"},
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
def team_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> CollaboratorTeamWebhookProcessor:
    return CollaboratorTeamWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestCollaboratorTeamWebhookProcessor:
    @pytest.mark.parametrize(
        "event_type,action,expected",
        [
            ("team", "added_to_repository", True),
            (
                "team",
                "removed_from_repository",
                False,
            ),  # Not in TEAM_COLLABORATOR_EVENTS
            ("member", "added", False),
            ("team", "unknown_action", False),
            ("team", None, False),
        ],
    )
    async def test_should_process_event(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        event_type: str,
        action: str,
        expected: bool,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": event_type}
        mock_event.payload = {"action": action}

        assert (
            await team_webhook_processor._should_process_event(mock_event) is expected
        )

    async def test_get_matching_kinds(
        self, team_webhook_processor: CollaboratorTeamWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        assert await team_webhook_processor.get_matching_kinds(mock_event) == [
            ObjectKind.COLLABORATOR
        ]

    @pytest.mark.parametrize(
        "payload,expected_result",
        [
            (VALID_TEAM_COLLABORATOR_PAYLOADS, True),
            (INVALID_TEAM_COLLABORATOR_PAYLOADS["invalid"], False),
            (INVALID_TEAM_COLLABORATOR_PAYLOADS["missing_repo"], False),
            (INVALID_TEAM_COLLABORATOR_PAYLOADS["missing_org"], False),
            (INVALID_TEAM_COLLABORATOR_PAYLOADS["missing_team"], False),
            (INVALID_TEAM_COLLABORATOR_PAYLOADS["missing_org_login"], False),
            (INVALID_TEAM_COLLABORATOR_PAYLOADS["missing_team_name"], False),
        ],
    )
    async def test_validate_payload(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        payload: dict[str, Any],
        expected_result: bool,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        mock_port_app_config.repository_type = "all"

        async with event_context("test_event") as event_context_obj:
            event_context_obj.port_app_config = mock_port_app_config
            assert (
                await team_webhook_processor._validate_payload(payload)
                is expected_result
            )

    @pytest.mark.parametrize(
        "action,expected_updated,expected_deleted",
        [
            ("added_to_repository", True, False),
            (
                "removed_from_repository",
                False,
                False,
            ),  # Not in TEAM_COLLABORATOR_EVENTS
            ("unknown_action", False, False),  # Not in TEAM_COLLABORATOR_EVENTS
        ],
    )
    async def test_handle_event_team_events(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        resource_config: ResourceConfig,
        action: str,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        # Set up payload
        payload = VALID_TEAM_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = action

        # Mock team data for GraphQL exporter
        mock_team_data = {
            "members": {
                "nodes": [
                    {
                        "id": "user1",
                        "login": "test-user",
                        "name": "Test User",
                        "isSiteAdmin": False,
                    }
                ]
            },
            "repositories": {
                "nodes": [
                    {"name": "repo1"},
                    {"name": "repo2"},
                ]
            },
        }

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.create_github_client"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            # Mock GraphQLTeamMembersAndReposExporter
            with patch(
                "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.GraphQLTeamMembersAndReposExporter"
            ) as mock_graphql_team_exporter_class:
                mock_graphql_team_exporter = MagicMock()
                mock_graphql_team_exporter_class.return_value = (
                    mock_graphql_team_exporter
                )

                mock_graphql_team_exporter.get_resource = AsyncMock(
                    return_value=mock_team_data
                )

                result = await team_webhook_processor.handle_event(
                    payload, resource_config
                )

                # Verify the result
                assert isinstance(result, WebhookEventRawResults)
                assert bool(result.updated_raw_results) is expected_updated
                assert bool(result.deleted_raw_results) is expected_deleted

                if expected_updated:
                    # Verify the data structure matches expected format
                    expected_team_data = [
                        {
                            "id": "user1",
                            "login": "test-user",
                            "name": "Test User",
                            "site_admin": False,
                            "__repository": "repo1",
                        },
                        {
                            "id": "user1",
                            "login": "test-user",
                            "name": "Test User",
                            "site_admin": False,
                            "__repository": "repo2",
                        },
                    ]
                    assert result.updated_raw_results == expected_team_data

                    # Verify GraphQL client was created with correct type
                    mock_create_client.assert_called_once_with(
                        client_type=GithubClientType.GRAPHQL
                    )

                    # Verify team exporter was called
                    mock_graphql_team_exporter.get_resource.assert_called_once_with(
                        {"slug": "test-team"}
                    )
                else:
                    # For unsupported events, no exporters should be called
                    mock_create_client.assert_not_called()
                    mock_graphql_team_exporter.get_resource.assert_not_called()

    async def test_handle_event_no_team_data(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling when no team data is returned."""
        payload = VALID_TEAM_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = "added_to_repository"

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.create_github_client"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            # Mock GraphQLTeamMembersAndReposExporter returning None
            with patch(
                "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.GraphQLTeamMembersAndReposExporter"
            ) as mock_graphql_team_exporter_class:
                mock_graphql_team_exporter = MagicMock()
                mock_graphql_team_exporter_class.return_value = (
                    mock_graphql_team_exporter
                )

                mock_graphql_team_exporter.get_resource = AsyncMock(return_value=None)

                result = await team_webhook_processor.handle_event(
                    payload, resource_config
                )

                # Verify empty results when no team data
                assert isinstance(result, WebhookEventRawResults)
                assert result.updated_raw_results == []
                assert result.deleted_raw_results == []

                # Verify GraphQL client was created
                mock_create_client.assert_called_once_with(
                    client_type=GithubClientType.GRAPHQL
                )
