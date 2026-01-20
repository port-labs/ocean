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
    ResourceConfig,
    Selector,
)

from webhook.processors.user_group_processor import (
    UserGroupWebhookProcessor,
)
from integration import ObjectKind
from tests.conftest import SAMPLE_USER_GROUP_DATA


@pytest.fixture
def resource_config() -> ResourceConfig:
    """Create a resource config fixture for user group."""
    return ResourceConfig(
        kind="sys_user_group",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".sys_id",
                    title=".name",
                    blueprint='"servicenowUserGroup"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def user_group_processor(
    mock_webhook_event: WebhookEvent,
) -> UserGroupWebhookProcessor:
    """Create a user group webhook processor fixture."""
    return UserGroupWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestUserGroupWebhookProcessor:
    """Test suite for UserGroupWebhookProcessor."""

    async def test_get_matching_kinds(
        self, user_group_processor: UserGroupWebhookProcessor
    ) -> None:
        """Test that get_matching_kinds returns the correct kind."""
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await user_group_processor.get_matching_kinds(mock_event)

        assert kinds == [ObjectKind.SYS_USER_GROUP]

    async def test_should_process_event_valid(
        self, user_group_processor: UserGroupWebhookProcessor
    ) -> None:
        """Test that _should_process_event returns True for correct class name."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {
            "roles": "test123",
            "manager": {
                "sys_id": "test123",
                "name": "test123",
            },
            "sys_id": "test123",
        }

        result = user_group_processor._should_process_event(mock_event)

        assert result is True

    async def test_should_process_event_invalid(
        self, user_group_processor: UserGroupWebhookProcessor
    ) -> None:
        """Test that _should_process_event returns False for incorrect class name."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_class_name": "incident", "sys_id": "test123"}

        result = user_group_processor._should_process_event(mock_event)

        assert result is False

    async def test_handle_event_found(
        self,
        user_group_processor: UserGroupWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling an event when the record is found."""
        payload = {
            "sys_id": SAMPLE_USER_GROUP_DATA["sys_id"],
            "roles": "test123",
            "manager": {
                "sys_id": "test123",
                "name": "test123",
            },
        }

        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(
            return_value=SAMPLE_USER_GROUP_DATA
        )

        with patch(
            "webhook.processors.user_group_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await user_group_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == [SAMPLE_USER_GROUP_DATA]
            assert result.deleted_raw_results == []

    async def test_handle_event_deleted(
        self,
        user_group_processor: UserGroupWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling an event when the record is not found."""
        payload = {
            "sys_id": "deleted_id",
            "roles": "test123",
            "manager": {
                "sys_id": "test123",
                "name": "test123",
            },
        }

        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(return_value=None)

        with patch(
            "webhook.processors.user_group_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await user_group_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == [payload]
