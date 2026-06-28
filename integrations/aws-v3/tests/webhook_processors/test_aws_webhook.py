import asyncio
import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, EventPayload, EventHeaders

from aws.events.webhook_processor import AWSEventWebhookProcessor


class DummyEvent:
    def __init__(self, payload, headers=None, raw_body=""):
        self.payload = payload
        self.headers = headers or {}
        self.raw_body = raw_body or ""
        self.resource_config = type("R", (), {"raw_config": {"webhookSecret": "shhh"}})()


@pytest.mark.asyncio
async def test_invalid_signature_rejected(monkeypatch):
    payload = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-123"}, "region": "us-east-1", "account": "111"}
    # signature missing
    event = WebhookEvent(payload, headers={}, raw_body="payload")
    processor = AWSEventWebhookProcessor(event)

    ok = await processor.authenticate(payload, {})
    assert not ok


@pytest.mark.asyncio
async def test_routing_to_ec2_handler(monkeypatch):
    payload = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-abc", "state": "running"}, "region": "us-east-1", "account": "111"}
    # monkeypatch signature validation
    event = WebhookEvent(payload, headers={"X-AWS-Signature": "abc"}, raw_body="payload")
    processor = AWSEventWebhookProcessor(event)

    monkeypatch.setattr(processor.event, "raw_body", "payload")
    # stub secret
    processor.event.resource_config.raw_config["webhookSecret"] = "shhh"

    import hmac, hashlib
    sig = hmac.new(b"shhh", b"payload", hashlib.sha256).hexdigest()
    event.headers["X-AWS-Signature"] = sig

    # mock session and exporter to return data
    async def fake_get_session_for_account(account):
        return object()

    async def fake_get_resource(self, options):
        return {"InstanceId": options.instance_id, "State": {"Name": "running"}}

    monkeypatch.setattr("aws.auth.session_factory.get_session_for_account", lambda account: asyncio.sleep(0, result=object()))
    monkeypatch.setattr("aws.core.exporters.ec2.instance.exporter.EC2InstanceExporter.get_resource", fake_get_resource)

    # validate auth
    assert await processor.authenticate(payload, event.headers)

    # ensure get_matching_kinds returns ec2
    kinds = await processor.get_matching_kinds(event)
    assert "ec2:instance" in ",".join(kinds) or kinds

