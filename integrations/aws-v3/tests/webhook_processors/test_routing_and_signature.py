import json
import hmac
import hashlib
import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from aws.events.webhook_processor import AWSEventWebhookProcessor
from aws.core.helpers.types import ObjectKind


@pytest.mark.asyncio
async def test_valid_event_routing_ec2():
    payload = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-rt"}, "region": "us-east-1", "account": "111"}
    event = WebhookEvent(payload, headers={}, raw_body=json.dumps(payload))
    event.resource_config = type("R", (), {"raw_config": {"webhookSecret": "x"}})()
    processor = AWSEventWebhookProcessor(event)

    kinds = await processor.get_matching_kinds(event)
    assert ObjectKind.EC2_INSTANCE in kinds


@pytest.mark.asyncio
async def test_invalid_and_valid_signature():
    payload = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-sig"}, "region": "us-east-1", "account": "111"}
    raw = json.dumps(payload, separators=(",", ":"))

    # invalid signature
    event_bad = WebhookEvent(payload, headers={"X-AWS-Signature": "bad"}, raw_body=raw)
    event_bad.resource_config = type("R", (), {"raw_config": {"webhookSecret": "secret"}})()
    proc_bad = AWSEventWebhookProcessor(event_bad)
    assert not await proc_bad.authenticate(payload, event_bad.headers)

    # valid signature
    sig = hmac.new(b"secret", raw.encode(), hashlib.sha256).hexdigest()
    event_good = WebhookEvent(payload, headers={"X-AWS-Signature": sig}, raw_body=raw)
    event_good.resource_config = event_bad.resource_config
    proc_good = AWSEventWebhookProcessor(event_good)
    assert await proc_good.authenticate(payload, event_good.headers)
