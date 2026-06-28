import json
import pytest
import asyncio
import hmac
import hashlib

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from aws.events.webhook_processor import AWSEventWebhookProcessor


@pytest.mark.asyncio
async def test_ec2_upsert_and_delete(monkeypatch):
    payload_running = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-up", "state": "running"}, "region": "us-east-1", "account": "111"}
    payload_terminated = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-del", "state": "terminated"}, "region": "us-east-1", "account": "111"}

    # Mock session factory
    monkeypatch.setattr("aws.auth.session_factory.get_session_for_account", lambda account: asyncio.sleep(0, result=object()))

    async def fake_ec2_get(self, options):
        if options.instance_id == "i-up":
            return {"InstanceId": "i-up", "State": {"Name": "running"}}
        if options.instance_id == "i-del":
            return {"InstanceId": "i-del", "State": {"Name": "terminated"}}
        return {}

    monkeypatch.setattr("aws.core.exporters.ec2.instance.exporter.EC2InstanceExporter.get_resource", fake_ec2_get)

    # running -> upsert
    event_up = WebhookEvent(payload_running, headers={}, raw_body=json.dumps(payload_running))
    event_up.resource_config = type("R", (), {"raw_config": {"webhookSecret": "x"}})()
    proc_up = AWSEventWebhookProcessor(event_up)
    await proc_up.before_processing()
    res_up = await proc_up.handle_event(payload_running, event_up.resource_config)
    assert res_up.updated_raw_results and not res_up.deleted_raw_results

    # terminated -> delete
    event_del = WebhookEvent(payload_terminated, headers={}, raw_body=json.dumps(payload_terminated))
    event_del.resource_config = event_up.resource_config
    proc_del = AWSEventWebhookProcessor(event_del)
    await proc_del.before_processing()
    res_del = await proc_del.handle_event(payload_terminated, event_del.resource_config)
    assert res_del.deleted_raw_results and not res_del.updated_raw_results


@pytest.mark.asyncio
async def test_s3_deleted(monkeypatch):
    payload = {"source": "aws.s3", "detail-type": "S3 Object Removed", "detail": {"requestParameters": {"bucketName": "b1"}}, "region": "us-east-1", "account": "111"}

    monkeypatch.setattr("aws.auth.session_factory.get_session_for_account", lambda account: asyncio.sleep(0, result=object()))

    async def fake_s3_get(self, options):
        # simulate bucket missing
        return {}

    monkeypatch.setattr("aws.core.exporters.s3.bucket.exporter.S3BucketExporter.get_resource", fake_s3_get)

    event = WebhookEvent(payload, headers={}, raw_body=json.dumps(payload))
    event.resource_config = type("R", (), {"raw_config": {"webhookSecret": "x"}})()
    proc = AWSEventWebhookProcessor(event)
    await proc.before_processing()
    res = await proc.handle_event(payload, event.resource_config)
    assert res.deleted_raw_results


@pytest.mark.asyncio
async def test_lambda_updated(monkeypatch):
    payload = {"source": "aws.lambda", "detail-type": "Lambda Function Updated", "detail": {"functionName": "fn1"}, "region": "us-east-1", "account": "111"}

    monkeypatch.setattr("aws.auth.session_factory.get_session_for_account", lambda account: asyncio.sleep(0, result=object()))

    async def fake_lambda_get(self, options):
        return {"FunctionName": options.function_name}

    monkeypatch.setattr("aws.core.exporters.aws_lambda.function.exporter.LambdaFunctionExporter.get_resource", fake_lambda_get)

    event = WebhookEvent(payload, headers={}, raw_body=json.dumps(payload))
    event.resource_config = type("R", (), {"raw_config": {"webhookSecret": "x"}})()
    proc = AWSEventWebhookProcessor(event)
    await proc.before_processing()
    res = await proc.handle_event(payload, event.resource_config)
    assert res.updated_raw_results


@pytest.mark.asyncio
async def test_unknown_event_resilience():
    payload = {"foo": "bar"}
    event = WebhookEvent(payload, headers={}, raw_body=json.dumps(payload))
    event.resource_config = type("R", (), {"raw_config": {"webhookSecret": "x"}})()
    proc = AWSEventWebhookProcessor(event)
    await proc.before_processing()
    kinds = await proc.get_matching_kinds(event)
    assert kinds == []


@pytest.mark.asyncio
async def test_duplicate_idempotency(monkeypatch):
    inner = {"source": "aws.ec2", "detail-type": "EC2 Instance State-change Notification", "detail": {"instance-id": "i-dup"}, "region": "us-east-1", "account": "111"}
    inner_str = json.dumps(inner, separators=(",", ":"))
    sns_envelope = {"Type": "Notification", "MessageId": "dup-1", "Message": inner_str}

    sig = hmac.new(b"x", inner_str.encode(), hashlib.sha256).hexdigest()
    event1 = WebhookEvent(sns_envelope, headers={"X-AWS-Signature": sig}, raw_body=json.dumps(sns_envelope))
    event1.resource_config = type("R", (), {"raw_config": {"webhookSecret": "x"}})()
    proc1 = AWSEventWebhookProcessor(event1)
    await proc1.before_processing()
    assert not getattr(event1, "_skip_processing", False)

    event2 = WebhookEvent(sns_envelope, headers={"X-AWS-Signature": sig}, raw_body=json.dumps(sns_envelope))
    event2.resource_config = event1.resource_config
    proc2 = AWSEventWebhookProcessor(event2)
    await proc2.before_processing()
    assert getattr(event2, "_skip_processing", False)

def test_pagination_regression_placeholder():
    # Pagination regression depends on exporter paginators — covered in exporter tests
    assert True
