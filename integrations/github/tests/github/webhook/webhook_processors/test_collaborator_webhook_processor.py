from github.webhook.events import (
    COLLABORATOR_EVENTS,
    TEAM_COLLABORATOR_EVENTS,
    COLLABORATOR_UPSERT_EVENTS,
)
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
from github.webhook.webhook_processors.collaborator_webhook_processor import (
    CollaboratorWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleCollaboratorOptions, SingleTeamOptions
from typing import Any, AsyncGenerator


VALID_MEMBER_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "action": "added",
    "repository": {"name": "test-repo"},
    "member": {"login": "test-user"},
}

VALID_MEMBERSHIP_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "action": "added",
    "repository": {"name": "test-repo"},
    "organization": {"login": "test-org"},
    "team": {"name": "test-team", "slug": "test-team"},
    "member": {"login": "test-user"},
}

VALID_TEAM_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "action": "added_to_repository",
    "repository": {"name": "test-repo"},
    "organization": {"login": "test-org"},
    "team": {"name": "test-team"},
}

INVALID_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "invalid": {
        "action": "invalid",
    },
    "unknown": {
        "action": "unknown",
    },
    "": {
        "action": "",
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
def collaborator_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> CollaboratorWebhookProcessor:
    return CollaboratorWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestCollaboratorWebhookProcessor:
    @pytest.mark.parametrize(
        "event_type,action,expected",
        [
            ("member", "added", True),
            ("member", "edited", True),
            ("member", "removed", True),
            ("membership", "added", True),
            ("team", "added_to_repository", True),
            ("repository", "added", False),
            ("member", "unknown_action", False),
            ("member", None, False),
        ],
    )
    async def test_should_process_event(
        self,
        collaborator_webhook_processor: CollaboratorWebhookProcessor,
        event_type: str,
        action: str,
        expected: bool,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": event_type}
        mock_event.payload = {"action": action}

        assert (
            await collaborator_webhook_processor._should_process_event(mock_event)
            is expected
        )

    async def test_get_matching_kinds(
        self, collaborator_webhook_processor: CollaboratorWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        assert await collaborator_webhook_processor.get_matching_kinds(mock_event) == [
            ObjectKind.COLLABORATOR
        ]

    @pytest.mark.parametrize(
        "event_type, events, payload, expected_result",
        [
            ("member", COLLABORATOR_EVENTS, VALID_MEMBER_COLLABORATOR_PAYLOADS, True),
            (
                "membership",
                COLLABORATOR_EVENTS,
                VALID_MEMBERSHIP_COLLABORATOR_PAYLOADS,
                True,
            ),
            ("team", TEAM_COLLABORATOR_EVENTS, VALID_TEAM_COLLABORATOR_PAYLOADS, True),
            ("member", COLLABORATOR_EVENTS, INVALID_COLLABORATOR_PAYLOADS, False),
            ("membership", COLLABORATOR_EVENTS, INVALID_COLLABORATOR_PAYLOADS, False),
            ("team", TEAM_COLLABORATOR_EVENTS, INVALID_COLLABORATOR_PAYLOADS, False),
        ],
    )
    async def test_validate_payload(
        self,
        collaborator_webhook_processor: CollaboratorWebhookProcessor,
        event_type: str,
        events: list[str],
        payload: dict[str, Any],
        expected_result: bool,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        mock_port_app_config.repository_type = "all"

        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": event_type},
            payload={"action": None},
        )
        for action in events:
            event.payload = {"action": action}
            await collaborator_webhook_processor._should_process_event(event)
            assert (
                await collaborator_webhook_processor.validate_payload(payload)
                is expected_result
            )

    @pytest.mark.parametrize(
        "event_type,payload,action,expected_updated,expected_deleted",
        [
            ("member", VALID_MEMBER_COLLABORATOR_PAYLOADS, "added", True, False),
            ("member", VALID_MEMBER_COLLABORATOR_PAYLOADS, "edited", True, False),
            ("member", VALID_MEMBER_COLLABORATOR_PAYLOADS, "removed", False, True),
            ("member", VALID_MEMBER_COLLABORATOR_PAYLOADS, "deleted", False, True),
            (
                "membership",
                VALID_MEMBERSHIP_COLLABORATOR_PAYLOADS,
                "added",
                True,
                False,
            ),
            (
                "team",
                VALID_TEAM_COLLABORATOR_PAYLOADS,
                "added_to_repository",
                True,
                False,
            ),
        ],
    )
    async def test_handle_event_member_events(
        self,
        collaborator_webhook_processor: CollaboratorWebhookProcessor,
        resource_config: ResourceConfig,
        event_type: str,
        payload: dict[str, Any],
        action: str,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        # Set up the event type
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": event_type}
        mock_event.payload = {"action": action}

        await collaborator_webhook_processor._should_process_event(mock_event)

        # Set up payload based on event type
        payload["action"] = action

        # Mock the collaborators data
        mock_collaborator_data = {
            "login": "test-user",
            "name": "Test User",
            "email": "test@example.com",
        }

        # Mock the repositories data for membership events
        mock_repositories = [
            {"name": "repo1", "full_name": "org/repo1"},
            {"name": "repo2", "full_name": "org/repo2"},
        ]

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.create_github_client"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            # Mock RestCollaboratorExporter
            with patch(
                "github.webhook.webhook_processors.collaborator_webhook_processor.RestCollaboratorExporter"
            ) as mock_exporter_class:
                mock_exporter = MagicMock()
                mock_exporter_class.return_value = mock_exporter
                mock_exporter.get_resource = AsyncMock(
                    return_value=mock_collaborator_data
                )

                # Mock RestTeamExporter for membership events
                with patch(
                    "github.webhook.webhook_processors.collaborator_webhook_processor.RestTeamExporter"
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

                    # Mock enrich_collaborators_with_repositories
                    with patch(
                        "github.webhook.webhook_processors.collaborator_webhook_processor.enrich_collaborators_with_repositories"
                    ) as mock_enrich:
                        enriched_data = {
                            **mock_collaborator_data,
                            "repositories": mock_repositories,
                        }
                        mock_enrich.return_value = enriched_data

                        result = await collaborator_webhook_processor.handle_event(
                            payload, resource_config
                        )

                        # Verify the result
                        assert isinstance(result, WebhookEventRawResults)
                        assert bool(result.updated_raw_results) is expected_updated
                        assert bool(result.deleted_raw_results) is expected_deleted

                        if expected_updated:
                            if (
                                event_type == "membership"
                                and action in COLLABORATOR_UPSERT_EVENTS
                            ):
                                assert result.updated_raw_results == [enriched_data]
                                mock_team_exporter.get_team_repositories_by_slug.assert_called_once_with(
                                    SingleTeamOptions(slug="test-team")
                                )
                                mock_enrich.assert_called_once_with(
                                    mock_collaborator_data, mock_repositories
                                )
                            else:
                                assert result.updated_raw_results == [
                                    mock_collaborator_data
                                ]

                        if expected_deleted:
                            if event_type == "team":
                                assert result.deleted_raw_results == ["test-org"]
                            else:
                                assert result.deleted_raw_results == ["test-user"]

                        # Verify exporter was called with correct options
                        if not expected_deleted:
                            if event_type == "team":
                                mock_exporter.get_resource.assert_called_once_with(
                                    SingleCollaboratorOptions(
                                        repo_name="test-repo", username="test-org"
                                    )
                                )
                            else:
                                mock_exporter.get_resource.assert_called_once_with(
                                    SingleCollaboratorOptions(
                                        repo_name="test-repo", username="test-user"
                                    )
                                )

    async def test_handle_event_membership_with_upsert_action(
        self,
        collaborator_webhook_processor: CollaboratorWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        # Set up the event type
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "membership"}
        mock_event.payload = {"action": "added"}

        await collaborator_webhook_processor._should_process_event(mock_event)

        payload = VALID_MEMBERSHIP_COLLABORATOR_PAYLOADS

        mock_collaborator_data = {
            "login": "test-user",
            "name": "Test User",
        }

        mock_repositories = [
            {"name": "repo1", "full_name": "org/repo1"},
        ]

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.create_github_client"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            with patch(
                "github.webhook.webhook_processors.collaborator_webhook_processor.RestCollaboratorExporter"
            ) as mock_exporter_class:
                mock_exporter = MagicMock()
                mock_exporter_class.return_value = mock_exporter
                mock_exporter.get_resource = AsyncMock(
                    return_value=mock_collaborator_data
                )

                with patch(
                    "github.webhook.webhook_processors.collaborator_webhook_processor.RestTeamExporter"
                ) as mock_team_exporter_class:
                    mock_team_exporter = MagicMock()
                    mock_team_exporter_class.return_value = mock_team_exporter

                    async def mock_get_team_repositories() -> (
                        AsyncGenerator[list[dict[str, Any]], None]
                    ):
                        yield mock_repositories

                    mock_team_exporter.get_team_repositories_by_slug.return_value = (
                        mock_get_team_repositories()
                    )

                    with patch(
                        "github.webhook.webhook_processors.collaborator_webhook_processor.enrich_collaborators_with_repositories"
                    ) as mock_enrich:
                        enriched_data = {
                            **mock_collaborator_data,
                            "repositories": mock_repositories,
                        }
                        mock_enrich.return_value = enriched_data

                        result = await collaborator_webhook_processor.handle_event(
                            payload, resource_config
                        )

                        assert isinstance(result, WebhookEventRawResults)
                        assert result.updated_raw_results == [enriched_data]
                        assert result.deleted_raw_results == []

                        # Verify team exporter was called
                        mock_team_exporter.get_team_repositories_by_slug.assert_called_once_with(
                            SingleTeamOptions(slug="test-team")
                        )
                        mock_enrich.assert_called_once_with(
                            mock_collaborator_data, mock_repositories
                        )
