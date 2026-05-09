import json
import asyncio
import hmac
import hashlib
import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from aws.events.webhook_processor import AWSEventWebhookProcessor


@pytest.mark.asyncio
async def test_sns_unwrap_and_signature(monkeypatch):
    inner = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-1"}, "region": "us-east-1", "account": "111"}
    inner_str = json.dumps(inner, separators=(",", ":"))

    sns_envelope = {
        "Type": "Notification",
        "MessageId": "msg-1",
        "TopicArn": "arn:aws:sns:us-east-1:111:topic",
        "Message": inner_str,
    }

    # compute signature using webhookSecret 'shhh'
    sig = hmac.new(b"shhh", inner_str.encode(), hashlib.sha256).hexdigest()

    # create WebhookEvent and processor
    event = WebhookEvent(sns_envelope, headers={"X-AWS-Signature": sig}, raw_body=json.dumps(sns_envelope))
    event.resource_config = type("R", (), {"raw_config": {"webhookSecret": "shhh"}})()
    processor = AWSEventWebhookProcessor(event)

    # run before_processing to unwrap
    await processor.before_processing()
    assert isinstance(event.payload, dict)
    assert event.payload.get("detail") and event.payload["detail"]["instance-id"] == "i-1"

    # signature should validate against the inner message
    assert await processor.authenticate(event.payload, event.headers)


@pytest.mark.asyncio
async def test_dedupe_skips_duplicate(monkeypatch):
    inner = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-2"}, "region": "us-east-1", "account": "111"}
    inner_str = json.dumps(inner, separators=(",", ":"))

    sns_envelope = {
        "Type": "Notification",
        "MessageId": "msg-dup",
        "TopicArn": "arn:aws:sns:us-east-1:111:topic",
        "Message": inner_str,
    }

    sig = hmac.new(b"shhh", inner_str.encode(), hashlib.sha256).hexdigest()

    event1 = WebhookEvent(sns_envelope, headers={"X-AWS-Signature": sig}, raw_body=json.dumps(sns_envelope))
    event1.resource_config = type("R", (), {"raw_config": {"webhookSecret": "shhh"}})()
    proc1 = AWSEventWebhookProcessor(event1)

    # first processing should not be skipped
    await proc1.before_processing()
    assert not getattr(event1, "_skip_processing", False)

    # second event with same MessageId should be marked skip
    event2 = WebhookEvent(sns_envelope, headers={"X-AWS-Signature": sig}, raw_body=json.dumps(sns_envelope))
    event2.resource_config = event1.resource_config
    proc2 = AWSEventWebhookProcessor(event2)
    await proc2.before_processing()
    assert getattr(event2, "_skip_processing", False)
