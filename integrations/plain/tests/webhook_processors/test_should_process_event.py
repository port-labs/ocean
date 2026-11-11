from unittest.mock import MagicMock

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from webhook_processors.company_webhook_processor import CompanyWebhookProcessor
from webhook_processors.customer_webhook_processor import CustomerWebhookProcessor
from webhook_processors.discussion_message_webhook_processor import (
    DiscussionMessageWebhookProcessor,
)
from webhook_processors.discussion_webhook_processor import DiscussionWebhookProcessor
from webhook_processors.machine_user_webhook_processor import (
    MachineUserWebhookProcessor,
)
from webhook_processors.tenant_webhook_processor import TenantWebhookProcessor
from webhook_processors.thread_message_webhook_processor import (
    ThreadMessageWebhookProcessor,
)
from webhook_processors.thread_webhook_processor import ThreadWebhookProcessor
from webhook_processors.user_webhook_processor import UserWebhookProcessor


def _event(event_type: str) -> WebhookEvent:
    return WebhookEvent(
        trace_id="t",
        payload={"type": event_type, "payload": {}},
        headers={},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("processor_cls", "matching", "non_matching"),
    [
        (
            ThreadWebhookProcessor,
            "thread.thread_created",
            "customer.customer_created",
        ),
        (
            CustomerWebhookProcessor,
            "customer.customer_created",
            "thread.thread_created",
        ),
        (
            UserWebhookProcessor,
            "thread.thread_assignment_transitioned",
            "thread.thread_created",
        ),
        (
            MachineUserWebhookProcessor,
            "thread.thread_assignment_transitioned",
            "customer.customer_created",
        ),
        (
            CompanyWebhookProcessor,
            "customer.customer_updated",
            "thread.thread_created",
        ),
        (
            TenantWebhookProcessor,
            "thread.thread_tenant_updated",
            "thread.thread_created",
        ),
        (
            ThreadMessageWebhookProcessor,
            "thread.email_received",
            "thread.thread_created",
        ),
        (
            DiscussionWebhookProcessor,
            "discussion.discussion_created",
            "thread.thread_created",
        ),
        (
            DiscussionMessageWebhookProcessor,
            "discussion.message_created",
            "thread.thread_created",
        ),
    ],
)
async def test_processor_filters_by_event_type(
    processor_cls: type,
    matching: str,
    non_matching: str,
) -> None:
    processor = processor_cls(_event(matching))
    assert await processor._should_process_event(_event(matching)) is True
    assert await processor._should_process_event(_event(non_matching)) is False


@pytest.mark.asyncio
async def test_should_process_event_requires_matching_type_before_signature() -> None:
    event = _event("customer.customer_created")
    event._original_request = MagicMock()
    processor = UserWebhookProcessor(event)

    assert await processor.should_process_event(event) is False
    event._original_request.body.assert_not_called()
