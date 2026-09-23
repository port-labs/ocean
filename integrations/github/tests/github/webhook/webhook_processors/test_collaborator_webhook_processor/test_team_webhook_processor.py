import httpx
from integration import (
    GithubCollaboratorConfig,
    GithubCollaboratorSelector,
    GithubPortAppConfig,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor import (
    CollaboratorTeamWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from typing import Any, AsyncGenerator
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
def resource_config() -> GithubCollaboratorConfig:
    return GithubCollaboratorConfig(
        kind=ObjectKind.COLLABORATOR,
        selector=GithubCollaboratorSelector(query="true", affiliation="all"),
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
            ("team", "removed_from_repository", True),
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

    async def test_handle_event_added_to_repository(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        resource_config: GithubCollaboratorConfig,
    ) -> None:
        payload = VALID_TEAM_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = "added_to_repository"

        rest_team_members_batch = [{"id": 1, "login": "test-user", "site_admin": False}]

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.create_github_client_for_org"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            async def mock_paginated_generator() -> (
                AsyncGenerator[list[dict[str, Any]], None]
            ):
                yield rest_team_members_batch

            mock_client.send_paginated_request.return_value = mock_paginated_generator()

            result = await team_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == [
                {
                    "id": 1,
                    "login": "test-user",
                    "site_admin": False,
                    "__repository": "test-repo",
                    "__organization": "test-org",
                }
            ]
            assert result.deleted_raw_results == []
            mock_create_client.assert_called_once_with("test-org")

    async def test_handle_event_removed_from_repository(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        resource_config: GithubCollaboratorConfig,
    ) -> None:
        payload = VALID_TEAM_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = "removed_from_repository"

        rest_team_members_batch = [
            {"id": 1, "login": "user-still-collaborator"},
            {"id": 2, "login": "user-no-longer-collaborator"},
        ]

        still_collaborator_data = {
            "login": "user-still-collaborator",
            "id": 1,
            "__repository": "test-repo",
            "__organization": "test-org",
        }

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.create_github_client_for_org"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            async def mock_paginated_generator() -> (
                AsyncGenerator[list[dict[str, Any]], None]
            ):
                yield rest_team_members_batch

            mock_client.send_paginated_request.return_value = mock_paginated_generator()

            with patch(
                "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.RestCollaboratorExporter"
            ) as mock_collab_exporter_class:
                mock_collab_exporter = MagicMock()
                mock_collab_exporter_class.return_value = mock_collab_exporter

                async def mock_get_resource(options: Any) -> dict[str, Any] | None:
                    if options["username"] == "user-still-collaborator":
                        return still_collaborator_data
                    return None

                mock_collab_exporter.get_resource = AsyncMock(
                    side_effect=mock_get_resource
                )

                result = await team_webhook_processor.handle_event(
                    payload, resource_config
                )

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert result.updated_raw_results[0] == still_collaborator_data
            assert len(result.deleted_raw_results) == 1
            assert (
                result.deleted_raw_results[0]["login"] == "user-no-longer-collaborator"
            )
            assert result.deleted_raw_results[0]["id"] == 2
            assert result.deleted_raw_results[0]["__repository"] == "test-repo"
            assert result.deleted_raw_results[0]["__organization"] == "test-org"

    async def test_handle_event_removed_from_repository_skips_member_on_error(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        resource_config: GithubCollaboratorConfig,
    ) -> None:
        payload = VALID_TEAM_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = "removed_from_repository"

        rest_team_members_batch = [
            {"id": 1, "login": "user-ok"},
            {"id": 2, "login": "user-error"},
        ]

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.create_github_client_for_org"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            async def mock_paginated_generator() -> (
                AsyncGenerator[list[dict[str, Any]], None]
            ):
                yield rest_team_members_batch

            mock_client.send_paginated_request.return_value = mock_paginated_generator()

            with patch(
                "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.RestCollaboratorExporter"
            ) as mock_collab_exporter_class:
                mock_collab_exporter = MagicMock()
                mock_collab_exporter_class.return_value = mock_collab_exporter

                async def mock_get_resource(options: Any) -> dict[str, Any] | None:
                    if options["username"] == "user-error":
                        raise httpx.HTTPStatusError(
                            "Server Error",
                            request=httpx.Request("GET", "https://api.github.com"),
                            response=httpx.Response(500),
                        )
                    return None

                mock_collab_exporter.get_resource = AsyncMock(
                    side_effect=mock_get_resource
                )

                result = await team_webhook_processor.handle_event(
                    payload, resource_config
                )

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert len(result.deleted_raw_results) == 1
            assert result.deleted_raw_results[0]["login"] == "user-ok"

    async def test_handle_event_unknown_action(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        resource_config: GithubCollaboratorConfig,
    ) -> None:
        payload = VALID_TEAM_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = "unknown_action"

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.create_github_client_for_org"
        ) as mock_create_client:
            result = await team_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == []
            mock_create_client.assert_not_called()

    async def test_handle_event_skips_when_affiliation_filter_enabled(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        resource_config: GithubCollaboratorConfig,
    ) -> None:
        payload = VALID_TEAM_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = "added_to_repository"

        # Enable affiliation filtering -> skip collaborator live events
        resource_config.selector.affiliation = "direct"

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.create_github_client_for_org"
        ) as mock_create_client:
            result = await team_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == []
            mock_create_client.assert_not_called()

    async def test_handle_event_no_team_data(
        self,
        team_webhook_processor: CollaboratorTeamWebhookProcessor,
        resource_config: GithubCollaboratorConfig,
    ) -> None:
        """Test handling when no team data is returned."""
        payload = VALID_TEAM_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = "added_to_repository"

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.team_webhook_processor.create_github_client_for_org"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            async def mock_paginated_generator() -> (
                AsyncGenerator[list[dict[str, Any]], None]
            ):
                yield []

            mock_client.send_paginated_request.return_value = mock_paginated_generator()

            result = await team_webhook_processor.handle_event(payload, resource_config)

            # Verify empty results when no team data
            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == []

            mock_create_client.assert_called_once_with("test-org")
