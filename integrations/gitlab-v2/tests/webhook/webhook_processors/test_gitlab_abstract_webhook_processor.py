import pytest

from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


class ConcreteGitlabWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["push"]
    hooks = ["Push Hook"]

    async def get_matching_kinds(self, event):  # type: ignore[no-untyped-def]
        return ["project"]

    async def handle_event(self, payload, resource_config):  # type: ignore[no-untyped-def]
        return None


@pytest.mark.asyncio
async def test_should_process_event_ignores_missing_gitlab_event_header() -> None:
    processor = ConcreteGitlabWebhookProcessor(
        event=WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "dependabot_alert"},
            payload={"event_name": "push"},
        )
    )

    assert await processor.should_process_event(processor.event) is False


@pytest.mark.asyncio
async def test_should_process_event_matches_gitlab_header_and_event() -> None:
    processor = ConcreteGitlabWebhookProcessor(
        event=WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Push Hook"},
            payload={"event_name": "push"},
        )
    )

    assert await processor.should_process_event(processor.event) is True
