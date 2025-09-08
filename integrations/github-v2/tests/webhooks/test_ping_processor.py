import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


@pytest.mark.asyncio
async def test_ping_processor_matches_and_handles():
    from github.webhooks_processors.processors.ping import GithubPingWebhookProcessor

    event = WebhookEvent(
        trace_id="t1",
        payload={"zen": "Keep it logically awesome", "hook": {}},
        headers={"X-GitHub-Event": "ping"},
    )

    p = GithubPingWebhookProcessor(event)
    assert await p.should_process_event(event) is True
    assert await p.validate_payload(event.payload) is True
    res = await p.handle_event(event.payload, resource_config=None)  # type: ignore[arg-type]
    assert res.updated_raw_results == [] and res.deleted_raw_results == []


