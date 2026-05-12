"""Tests for `aws.webhook.registry`."""

import pytest

from aws.webhook.registry import WEBHOOK_PATH, ocean, register_live_events_webhooks
from aws.webhook.processors.ec2_instance_processor import EC2InstanceWebhookProcessor
from aws.webhook.processors.ecs_service_processor import EcsServiceWebhookProcessor
from aws.webhook.processors.lambda_function_processor import (
    LambdaFunctionWebhookProcessor,
)
from aws.webhook.processors.s3_bucket_processor import S3BucketWebhookProcessor


def test_register_live_events_webhooks_registers_four_processors_on_one_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`register_live_events_webhooks()` should call `ocean.add_webhook_processor`
    exactly four times, all targeting `WEBHOOK_PATH`, one per kind."""

    calls: list[tuple[str, object]] = []

    def fake_add(path: str, processor: object) -> None:
        calls.append((path, processor))

    monkeypatch.setattr(ocean, "add_webhook_processor", fake_add)

    register_live_events_webhooks()

    assert calls == [
        (WEBHOOK_PATH, EC2InstanceWebhookProcessor),
        (WEBHOOK_PATH, EcsServiceWebhookProcessor),
        (WEBHOOK_PATH, LambdaFunctionWebhookProcessor),
        (WEBHOOK_PATH, S3BucketWebhookProcessor),
    ]
