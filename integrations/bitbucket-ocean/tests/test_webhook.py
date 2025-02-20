import pytest
import logging
from bitbucket_ocean.webhook import BitbucketWebhook

@pytest.mark.asyncio
async def test_handle_event(mocker):
    trace_id = "123456"
    payload = {"event": "repo:push"}
    headers = {"Content-Type": "application/json"}

    webhook = BitbucketWebhook(trace_id, payload, headers)
    mocker.patch.object(logging, "info")

    await webhook.handle_event(payload)

    logging.info.assert_called_with("Webhook event received: {'event': 'repo:push'}")
