from __future__ import annotations

from port_ocean.context.ocean import ocean

from aws.webhook.events import WEBHOOK_PATH
from aws.webhook.processors.ec2_instance import EC2InstanceWebhookProcessor
from aws.webhook.processors.ecs_service import ECSServiceWebhookProcessor
from aws.webhook.processors.lambda_function import LambdaFunctionWebhookProcessor
from aws.webhook.processors.s3_bucket import S3BucketWebhookProcessor
from aws.webhook.processors.sns_subscription import (
    SnsSubscriptionConfirmationProcessor,
)


def register_live_events_webhooks() -> None:
    """Register every AWS live-event processor on the shared webhook path."""
    ocean.add_webhook_processor(WEBHOOK_PATH, SnsSubscriptionConfirmationProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, EC2InstanceWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, ECSServiceWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, LambdaFunctionWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, S3BucketWebhookProcessor)


__all__ = ["register_live_events_webhooks", "WEBHOOK_PATH"]
