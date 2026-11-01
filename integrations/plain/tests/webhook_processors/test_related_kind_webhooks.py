from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from plain.exceptions import PlainGraphQLError
from plain.utils import ObjectKind
from webhook_processors.company_webhook_processor import CompanyWebhookProcessor
from webhook_processors.discussion_message_webhook_processor import (
    DiscussionMessageWebhookProcessor,
)
from webhook_processors.discussion_webhook_processor import DiscussionWebhookProcessor
from webhook_processors.tenant_webhook_processor import TenantWebhookProcessor
from webhook_processors.thread_message_webhook_processor import (
    ThreadMessageWebhookProcessor,
)
from webhook_processors.machine_user_webhook_processor import (
    MachineUserWebhookProcessor,
)
from webhook_processors.user_webhook_processor import UserWebhookProcessor


def _event(payload: dict[str, Any]) -> WebhookEvent:
    event = WebhookEvent(trace_id="test", payload=payload, headers={})
    event._original_request = MagicMock()
    event._original_request.body = AsyncMock(return_value=b"{}")
    return event


def _resource_config(kind: str) -> ResourceConfig:
    return ResourceConfig(
        kind=kind,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint='"x"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )


@pytest.mark.asyncio
async def test_company_from_customer_event() -> None:
    processor = CompanyWebhookProcessor(
        event=_event(
            {
                "type": "customer.customer_created",
                "payload": {"customer": {"id": "c_1"}},
            }
        )
    )
    with patch(
        "webhook_processors.company_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_customer = AsyncMock(
            return_value={"id": "c_1", "company": {"id": "co_1"}}
        )
        client.get_company = AsyncMock(
            return_value={"id": "co_1", "name": "Acme", "domainName": "acme.com"}
        )
        result = await processor.handle_event(
            processor.event.payload, _resource_config(ObjectKind.COMPANY)
        )

    assert result.updated_raw_results[0]["id"] == "co_1"


@pytest.mark.asyncio
async def test_tenant_from_thread_tenant_updated() -> None:
    processor = TenantWebhookProcessor(
        event=_event(
            {
                "type": "thread.thread_tenant_updated",
                "payload": {"tenant": {"id": "te_1"}, "thread": {"id": "th_1"}},
            }
        )
    )
    with patch("webhook_processors.tenant_webhook_processor.PlainClient") as client_cls:
        client = client_cls.return_value
        client.get_tenant = AsyncMock(return_value={"id": "te_1", "name": "Tenant"})
        result = await processor.handle_event(
            processor.event.payload, _resource_config(ObjectKind.TENANT)
        )

    assert result.updated_raw_results == [{"id": "te_1", "name": "Tenant"}]


@pytest.mark.asyncio
async def test_user_from_assignment() -> None:
    processor = UserWebhookProcessor(
        event=_event(
            {
                "type": "thread.thread_assignment_transitioned",
                "payload": {
                    "thread": {
                        "id": "th_1",
                        "assignee": {
                            "id": "us_1",
                            "email": "ada@example.com",
                            "fullName": "Ada",
                        },
                    }
                },
            }
        )
    )
    with patch("webhook_processors.user_webhook_processor.PlainClient") as client_cls:
        client = client_cls.return_value
        client.get_user = AsyncMock(
            return_value={"id": "us_1", "fullName": "Ada", "email": "ada@example.com"}
        )
        result = await processor.handle_event(
            processor.event.payload, _resource_config(ObjectKind.USER)
        )

    assert result.updated_raw_results[0]["id"] == "us_1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "assignee",
    [
        {"id": "mu_1", "fullName": "Support Bot"},
        {"__typename": "MachineUser", "id": "mu_1"},
        {"type": "MachineUser", "id": "mu_1"},
        {"id": "mu_1"},
    ],
)
async def test_machine_user_from_assignment(assignee: dict[str, str]) -> None:
    processor = MachineUserWebhookProcessor(
        event=_event(
            {
                "type": "thread.thread_assignment_transitioned",
                "payload": {
                    "thread": {
                        "id": "th_1",
                        "assignee": assignee,
                    }
                },
            }
        )
    )
    with patch(
        "webhook_processors.machine_user_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_machine_user = AsyncMock(
            return_value={
                "id": "mu_1",
                "fullName": "Support Bot",
                "isDeleted": False,
            }
        )
        result = await processor.handle_event(
            processor.event.payload, _resource_config(ObjectKind.MACHINE_USER)
        )

    assert result.updated_raw_results[0]["id"] == "mu_1"


@pytest.mark.asyncio
async def test_machine_user_skips_system_assignee() -> None:
    processor = MachineUserWebhookProcessor(
        event=_event(
            {
                "type": "thread.thread_assignment_transitioned",
                "payload": {
                    "thread": {
                        "id": "th_1",
                        # System assignees are id-only in webhook payloads.
                        "assignee": {"id": "sys_1"},
                    }
                },
            }
        )
    )
    with patch(
        "webhook_processors.machine_user_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_machine_user = AsyncMock()
        result = await processor.handle_event(
            processor.event.payload, _resource_config(ObjectKind.MACHINE_USER)
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    client.get_machine_user.assert_not_called()


@pytest.mark.asyncio
async def test_machine_user_deleted_when_excluded() -> None:
    from integration import MachineUserResourceConfig, MachineUserSelector

    processor = MachineUserWebhookProcessor(
        event=_event(
            {
                "type": "thread.thread_assignment_transitioned",
                "payload": {
                    "thread": {
                        "id": "th_1",
                        "assignee": {"id": "mu_1", "fullName": "Gone Bot"},
                    }
                },
            }
        )
    )
    resource = MachineUserResourceConfig(
        kind=ObjectKind.MACHINE_USER,
        selector=MachineUserSelector(query="true", excludeDeleted=True),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".fullName",
                    blueprint='"plainMachineUser"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )
    with patch(
        "webhook_processors.machine_user_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_machine_user = AsyncMock(
            return_value={"id": "mu_1", "fullName": "Gone Bot", "isDeleted": True}
        )
        result = await processor.handle_event(processor.event.payload, resource)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results[0]["id"] == "mu_1"


@pytest.mark.asyncio
async def test_thread_message_from_email_received() -> None:
    processor = ThreadMessageWebhookProcessor(
        event=_event(
            {
                "type": "thread.email_received",
                "payload": {
                    "thread": {"id": "th_1", "customer": {"id": "c_1"}},
                    "email": {"timelineEntryId": "tl_1"},
                },
            }
        )
    )
    with patch(
        "webhook_processors.thread_message_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_timeline_entry = AsyncMock(
            return_value={"id": "tl_1", "threadId": "th_1", "llmText": "Hello"}
        )
        result = await processor.handle_event(
            processor.event.payload, _resource_config(ObjectKind.THREAD_MESSAGE)
        )

    assert result.updated_raw_results[0]["id"] == "tl_1"


@pytest.mark.asyncio
async def test_thread_message_deletes_when_text_is_cleared() -> None:
    processor = ThreadMessageWebhookProcessor(
        event=_event(
            {
                "type": "timeline.timeline_entry_changed",
                "payload": {
                    "changeType": "ADDED",
                    "timelineEntry": {"id": "tl_1", "customerId": "c_1"},
                },
            }
        )
    )
    with patch(
        "webhook_processors.thread_message_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_timeline_entry = AsyncMock(
            side_effect=PlainGraphQLError(
                [{"message": "Plain timeline entry 'tl_1' has no message text"}]
            )
        )
        result = await processor.handle_event(
            processor.event.payload, _resource_config(ObjectKind.THREAD_MESSAGE)
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "tl_1"}]


@pytest.mark.asyncio
async def test_thread_message_deletes_when_timeline_entry_is_missing() -> None:
    processor = ThreadMessageWebhookProcessor(
        event=_event(
            {
                "type": "timeline.timeline_entry_changed",
                "payload": {
                    "changeType": "UPDATED",
                    "timelineEntry": {"id": "tl_gone", "customerId": "c_1"},
                },
            }
        )
    )
    with patch(
        "webhook_processors.thread_message_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_timeline_entry = AsyncMock(
            side_effect=PlainGraphQLError(
                [{"message": "Plain timeline entry 'tl_gone' was not found"}]
            )
        )
        result = await processor.handle_event(
            processor.event.payload, _resource_config(ObjectKind.THREAD_MESSAGE)
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "tl_gone"}]


@pytest.mark.asyncio
async def test_thread_message_deletes_removed_previous_timeline_entry() -> None:
    processor = ThreadMessageWebhookProcessor(
        event=_event(
            {
                "type": "timeline.timeline_entry_changed",
                "payload": {
                    "changeType": "REMOVED",
                    "timelineEntry": None,
                    "previousTimelineEntry": {
                        "id": "tl_removed",
                        "customerId": "c_1",
                    },
                },
            }
        )
    )
    result = await processor.handle_event(
        processor.event.payload, _resource_config(ObjectKind.THREAD_MESSAGE)
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "tl_removed"}]


@pytest.mark.asyncio
async def test_discussion_tool_call_approval_accepts_top_level_discussion_id() -> None:
    processor = DiscussionWebhookProcessor(
        event=_event(
            {
                "type": "discussion.tool_call_approval_resolved",
                "payload": {
                    "discussionId": "disc_1",
                    "approvalId": "apr_1",
                    "status": "APPROVED",
                },
            }
        )
    )
    with patch(
        "webhook_processors.discussion_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_discussion = AsyncMock(
            return_value={
                "id": "disc_1",
                "threadId": "th_1",
                "agentStatus": "IDLE",
            }
        )
        result = await processor.handle_event(
            processor.event.payload,
            _resource_config(ObjectKind.DISCUSSION),
        )

    assert result.updated_raw_results[0]["id"] == "disc_1"
    client.get_discussion.assert_awaited_once_with("disc_1")


@pytest.mark.asyncio
async def test_discussion_and_message_webhooks() -> None:
    discussion_processor = DiscussionWebhookProcessor(
        event=_event(
            {
                "type": "discussion.discussion_created",
                "payload": {"discussion": {"id": "disc_1", "threadId": "th_1"}},
            }
        )
    )
    with patch(
        "webhook_processors.discussion_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_discussion = AsyncMock(
            return_value={"id": "disc_1", "threadId": "th_1", "title": "Slack"}
        )
        result = await discussion_processor.handle_event(
            discussion_processor.event.payload,
            _resource_config(ObjectKind.DISCUSSION),
        )
    assert result.updated_raw_results[0]["id"] == "disc_1"

    message_processor = DiscussionMessageWebhookProcessor(
        event=_event(
            {
                "type": "discussion.message_created",
                "payload": {
                    "discussion": {"id": "disc_1", "threadId": "th_1"},
                    "message": {"id": "dm_1"},
                },
            }
        )
    )
    with patch(
        "webhook_processors.discussion_message_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_discussion_message = AsyncMock(
            return_value={
                "id": "dm_1",
                "threadDiscussionId": "disc_1",
                "threadId": "th_1",
                "text": "hi",
            }
        )
        result = await message_processor.handle_event(
            message_processor.event.payload,
            _resource_config(ObjectKind.DISCUSSION_MESSAGE),
        )
    assert result.updated_raw_results[0]["threadId"] == "th_1"


@pytest.mark.asyncio
async def test_thread_message_webhook_deletes_done_when_excluded() -> None:
    from integration import ThreadMessageResourceConfig, ThreadSelector

    processor = ThreadMessageWebhookProcessor(
        event=_event(
            {
                "type": "thread.email_received",
                "payload": {
                    "thread": {"id": "th_1", "customer": {"id": "c_1"}},
                    "email": {"timelineEntryId": "tl_1"},
                },
            }
        )
    )
    resource = ThreadMessageResourceConfig(
        kind=ObjectKind.THREAD_MESSAGE,
        selector=ThreadSelector(query="true", excludeDoneThreads=True),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint='"plainThreadMessage"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )
    with patch(
        "webhook_processors.thread_message_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_timeline_entry = AsyncMock(
            return_value={"id": "tl_1", "threadId": "th_1", "llmText": "Hello"}
        )
        client.get_thread = AsyncMock(return_value={"id": "th_1", "status": "DONE"})
        result = await processor.handle_event(processor.event.payload, resource)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results[0]["id"] == "tl_1"
    client.get_thread.assert_awaited_once_with("th_1")


@pytest.mark.asyncio
async def test_discussion_webhook_deletes_done_when_excluded() -> None:
    from integration import DiscussionResourceConfig, DiscussionSelector

    processor = DiscussionWebhookProcessor(
        event=_event(
            {
                "type": "discussion.discussion_created",
                "payload": {"discussion": {"id": "disc_1", "threadId": "th_1"}},
            }
        )
    )
    resource = DiscussionResourceConfig(
        kind=ObjectKind.DISCUSSION,
        selector=DiscussionSelector(
            query="true", excludeDoneThreads=True, excludeAiDiscussions=False
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"plainDiscussion"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )
    with patch(
        "webhook_processors.discussion_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_discussion = AsyncMock(
            return_value={"id": "disc_1", "threadId": "th_1", "title": "Slack"}
        )
        client.get_thread = AsyncMock(return_value={"id": "th_1", "status": "DONE"})
        result = await processor.handle_event(processor.event.payload, resource)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results[0]["id"] == "disc_1"
    client.get_thread.assert_awaited_once_with("th_1")


@pytest.mark.asyncio
async def test_discussion_message_webhook_deletes_done_when_excluded() -> None:
    from integration import DiscussionMessageResourceConfig, DiscussionSelector

    processor = DiscussionMessageWebhookProcessor(
        event=_event(
            {
                "type": "discussion.message_created",
                "payload": {
                    "discussion": {"id": "disc_1", "threadId": "th_1"},
                    "message": {"id": "dm_1"},
                },
            }
        )
    )
    resource = DiscussionMessageResourceConfig(
        kind=ObjectKind.DISCUSSION_MESSAGE,
        selector=DiscussionSelector(
            query="true", excludeDoneThreads=True, excludeAiDiscussions=False
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint='"plainDiscussionMessage"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )
    with patch(
        "webhook_processors.discussion_message_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_thread = AsyncMock(return_value={"id": "th_1", "status": "DONE"})
        result = await processor.handle_event(processor.event.payload, resource)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results[0]["id"] == "dm_1"
    client.get_thread.assert_awaited_once_with("th_1")
    client.get_discussion_message.assert_not_called()


@pytest.mark.asyncio
async def test_discussion_webhook_deletes_ai_when_excluded() -> None:
    from integration import DiscussionResourceConfig, DiscussionSelector

    processor = DiscussionWebhookProcessor(
        event=_event(
            {
                "type": "discussion.discussion_created",
                "payload": {"discussion": {"id": "disc_ai", "threadId": "th_1"}},
            }
        )
    )
    resource = DiscussionResourceConfig(
        kind=ObjectKind.DISCUSSION,
        selector=DiscussionSelector(
            query="true", excludeDoneThreads=False, excludeAiDiscussions=True
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"plainDiscussion"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )
    with patch(
        "webhook_processors.discussion_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_discussion = AsyncMock(
            return_value={
                "id": "disc_ai",
                "channelDetails": {
                    "__typename": "ThreadDiscussionAgentSessionChannelDetails"
                },
            }
        )
        result = await processor.handle_event(processor.event.payload, resource)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results[0]["id"] == "disc_ai"


@pytest.mark.asyncio
async def test_discussion_message_webhook_deletes_ai_when_excluded() -> None:
    from integration import DiscussionMessageResourceConfig, DiscussionSelector

    processor = DiscussionMessageWebhookProcessor(
        event=_event(
            {
                "type": "discussion.message_created",
                "payload": {
                    "discussion": {"id": "disc_ai", "threadId": "th_1"},
                    "message": {"id": "dm_ai"},
                },
            }
        )
    )
    resource = DiscussionMessageResourceConfig(
        kind=ObjectKind.DISCUSSION_MESSAGE,
        selector=DiscussionSelector(
            query="true", excludeDoneThreads=False, excludeAiDiscussions=True
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint='"plainDiscussionMessage"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )
    with patch(
        "webhook_processors.discussion_message_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_discussion = AsyncMock(
            return_value={
                "id": "disc_ai",
                "channelDetails": {
                    "__typename": (
                        "ThreadDiscussionCursorWorkspaceBackgroundAgentChannelDetails"
                    )
                },
            }
        )
        result = await processor.handle_event(processor.event.payload, resource)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results[0]["id"] == "dm_ai"
    client.get_discussion_message.assert_not_called()
