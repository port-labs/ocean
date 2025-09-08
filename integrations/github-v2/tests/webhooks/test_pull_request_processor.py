import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


@pytest.mark.asyncio
async def test_pull_request_processor_emits_pr_with_repository():
    from github.webhooks_processors.processors.pull_request import (
        GithubPullRequestWebhookProcessor,
    )

    payload = {
        "action": "opened",
        "repository": {"name": "booklibrary"},
        "pull_request": {"id": 10, "number": 5, "title": "PR"},
    }
    headers = {"X-GitHub-Event": "pull_request"}
    event = WebhookEvent(trace_id="t4", payload=payload, headers=headers)

    p = GithubPullRequestWebhookProcessor(event)
    assert await p.should_process_event(event) is True
    assert await p.validate_payload(payload) is True
    res = await p.handle_event(payload, resource_config=None)  # type: ignore[arg-type]
    assert len(res.updated_raw_results) == 1
    assert res.updated_raw_results[0]["__repository"] == "booklibrary"


