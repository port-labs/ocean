import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


@pytest.mark.asyncio
async def test_repository_processor_emits_repo():
    from github.webhooks_processors.processors.repository import (
        GithubRepositoryWebhookProcessor,
    )

    payload = {"action": "created", "repository": {"name": "booklibrary"}}
    headers = {"X-GitHub-Event": "repository"}
    event = WebhookEvent(trace_id="t3", payload=payload, headers=headers)

    p = GithubRepositoryWebhookProcessor(event)
    assert await p.should_process_event(event) is True
    assert await p.validate_payload(payload) is True
    res = await p.handle_event(payload, resource_config=None)  # type: ignore[arg-type]
    assert len(res.updated_raw_results) == 1
    assert res.updated_raw_results[0]["name"] == "booklibrary"


