import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


@pytest.mark.asyncio
async def test_issue_processor_emits_issue_with_repository():
    from github.webhooks_processors.processors.issue import GithubIssueWebhookProcessor

    payload = {
        "action": "opened",
        "repository": {"name": "booklibrary"},
        "issue": {"id": 1, "number": 1, "title": "Test"},
    }
    headers = {"X-GitHub-Event": "issues"}
    event = WebhookEvent(trace_id="t2", payload=payload, headers=headers)

    p = GithubIssueWebhookProcessor(event)
    assert await p.should_process_event(event) is True
    assert await p.validate_payload(payload) is True
    res = await p.handle_event(payload, resource_config=None)  # type: ignore[arg-type]
    assert len(res.updated_raw_results) == 1
    assert res.updated_raw_results[0]["__repository"] == "booklibrary"


