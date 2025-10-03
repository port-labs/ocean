from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.events import USER_DELETE_EVENTS, USER_UPSERT_EVENTS
from github.core.options import SingleUserOptions

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.user_webhook_processor import (
    UserWebhookProcessor,
)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.USER,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".login",
                    title=".login",
                    blueprint='"githubUser"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def user_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> UserWebhookProcessor:
    return UserWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestUserWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,action,result",
        [
            ("organization", USER_UPSERT_EVENTS[0], True),
            ("organization", USER_DELETE_EVENTS[0], True),
            ("organization", "some_other_action", False),
            ("invalid", USER_UPSERT_EVENTS[0], False),
            ("invalid", "some_other_action", False),
        ],
    )
    async def test_should_process_event(
        self,
        user_webhook_processor: UserWebhookProcessor,
        github_event: str,
        action: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request
        assert await user_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, user_webhook_processor: UserWebhookProcessor
    ) -> None:
        kinds = await user_webhook_processor.get_matching_kinds(
            user_webhook_processor.event
        )
        assert ObjectKind.USER in kinds

    @pytest.mark.parametrize(
        "action,is_deletion,expected_updated,expected_deleted",
        [
            ("member_added", False, True, False),
            ("member_removed", True, False, True),
        ],
    )
    async def test_handle_event_create_and_delete(
        self,
        user_webhook_processor: UserWebhookProcessor,
        resource_config: ResourceConfig,
        action: str,
        is_deletion: bool,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        user_data = {
            "id": 123,
            "login": "test-user",
            "node_id": "test-node-id",
            "type": "User",
        }

        payload = {
            "action": action,
            "membership": {"user": user_data},
            "organization": {"login": "test-org"},
        }

        if is_deletion:
            result = await user_webhook_processor.handle_event(payload, resource_config)
        else:
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = user_data

            with patch(
                "github.webhook.webhook_processors.user_webhook_processor.GraphQLUserExporter",
                return_value=mock_exporter,
            ):
                result = await user_webhook_processor.handle_event(
                    payload, resource_config
                )

            mock_exporter.get_resource.assert_called_once_with(
                SingleUserOptions(login="test-user")
            )

        assert isinstance(result, WebhookEventRawResults)
        assert bool(result.updated_raw_results) is expected_updated
        assert bool(result.deleted_raw_results) is expected_deleted

        if expected_updated:
            assert result.updated_raw_results == [user_data]

        if expected_deleted:
            assert result.deleted_raw_results == [user_data]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "action": USER_UPSERT_EVENTS[0],
                    "membership": {"user": {"login": "user1"}},
                    "organization": {"login": "test-org"},
                },
                True,
            ),
            (
                {
                    "action": USER_DELETE_EVENTS[0],
                    "membership": {"user": {"login": "user2"}},
                    "organization": {"login": "test-org"},
                },
                True,
            ),
            ({"action": USER_UPSERT_EVENTS[0]}, False),  # missing membership
            ({"membership": {"user": {"login": "user4"}}}, False),  # missing action
            (
                {"action": USER_UPSERT_EVENTS[0], "membership": {}},  # no user
                False,
            ),
            (
                {
                    "action": USER_UPSERT_EVENTS[0],
                    "membership": {"user": {}},
                },  # no login
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        user_webhook_processor: UserWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await user_webhook_processor.validate_payload(payload)
        assert result is expected
