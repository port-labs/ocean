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
from github.webhook.webhook_processors.collaborator_webhook_processor.member_webhook_processor import (
    CollaboratorMemberWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleCollaboratorOptions
from typing import Any
from port_ocean.context.event import event_context


VALID_MEMBER_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "action": "added",
    "repository": {"name": "test-repo"},
    "member": {"id": 1, "login": "test-user"},
}

INVALID_MEMBER_COLLABORATOR_PAYLOADS: dict[str, Any] = {
    "invalid": {
        "action": "invalid",
    },
    "missing_member": {
        "action": "added",
        "repository": {"name": "test-repo"},
    },
    "missing_login": {
        "action": "added",
        "repository": {"name": "test-repo"},
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
def member_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> CollaboratorMemberWebhookProcessor:
    return CollaboratorMemberWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestCollaboratorMemberWebhookProcessor:
    @pytest.mark.parametrize(
        "event_type,action,expected",
        [
            ("member", "added", True),
            ("member", "edited", True),
            ("member", "removed", True),
            ("repository", "added", False),
            ("member", "unknown_action", False),
            ("member", None, False),
        ],
    )
    async def test_should_process_event(
        self,
        member_webhook_processor: CollaboratorMemberWebhookProcessor,
        event_type: str,
        action: str,
        expected: bool,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": event_type}
        mock_event.payload = {"action": action}

        assert (
            await member_webhook_processor._should_process_event(mock_event) is expected
        )

    async def test_get_matching_kinds(
        self, member_webhook_processor: CollaboratorMemberWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        assert await member_webhook_processor.get_matching_kinds(mock_event) == [
            ObjectKind.COLLABORATOR
        ]

    @pytest.mark.parametrize(
        "payload,expected_result",
        [
            (VALID_MEMBER_COLLABORATOR_PAYLOADS, True),
            (INVALID_MEMBER_COLLABORATOR_PAYLOADS["invalid"], False),
            (INVALID_MEMBER_COLLABORATOR_PAYLOADS["missing_member"], False),
            (INVALID_MEMBER_COLLABORATOR_PAYLOADS["missing_login"], False),
        ],
    )
    async def test_validate_payload(
        self,
        member_webhook_processor: CollaboratorMemberWebhookProcessor,
        payload: dict[str, Any],
        expected_result: bool,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        mock_port_app_config.repository_type = "all"

        async with event_context("test_event") as event_context_obj:
            event_context_obj.port_app_config = mock_port_app_config
            assert (
                await member_webhook_processor._validate_payload(payload)
                is expected_result
            )

    @pytest.mark.parametrize(
        "action,expected_updated,expected_deleted",
        [
            ("added", True, False),
            ("edited", True, False),
            ("removed", False, True),
            ("deleted", False, True),
        ],
    )
    async def test_handle_event_member_events(
        self,
        member_webhook_processor: CollaboratorMemberWebhookProcessor,
        resource_config: ResourceConfig,
        action: str,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        # Set up payload
        payload = VALID_MEMBER_COLLABORATOR_PAYLOADS.copy()
        payload["action"] = action

        # Mock the collaborators data
        mock_collaborator_data = {
            "login": "test-user",
            "name": "Test User",
            "email": "test@example.com",
        }

        with patch(
            "github.webhook.webhook_processors.collaborator_webhook_processor.member_webhook_processor.create_github_client"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            # Mock RestCollaboratorExporter
            with patch(
                "github.webhook.webhook_processors.collaborator_webhook_processor.member_webhook_processor.RestCollaboratorExporter"
            ) as mock_exporter_class:
                mock_exporter = MagicMock()
                mock_exporter_class.return_value = mock_exporter
                mock_exporter.get_resource = AsyncMock(
                    return_value=mock_collaborator_data
                )

                result = await member_webhook_processor.handle_event(
                    payload, resource_config
                )

                # Verify the result
                assert isinstance(result, WebhookEventRawResults)
                assert bool(result.updated_raw_results) is expected_updated
                assert bool(result.deleted_raw_results) is expected_deleted

                if expected_updated:
                    assert result.updated_raw_results == [mock_collaborator_data]
                    mock_exporter.get_resource.assert_called_once_with(
                        SingleCollaboratorOptions(
                            repo_name="test-repo", username="test-user"
                        )
                    )

                if expected_deleted:
                    expected_deleted_data = {
                        "login": "test-user",
                        "id": 1,
                        "__repository": "test-repo",
                    }
                    assert result.deleted_raw_results == [expected_deleted_data]
                    mock_exporter.get_resource.assert_not_called()
