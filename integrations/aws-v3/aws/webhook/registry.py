"""Registry for AWS-V3 live-event webhook processors.

Mirrors the structure of `integrations/github/github/webhook/registry.py`.
The healthcheck processor is registered first so it short-circuits the
manual `curl` smoke-test path before any kind-specific processor looks
at the event.
"""

from __future__ import annotations

from port_ocean.context.ocean import ocean

from aws.webhook.middleware import register_live_events_auth_middleware
from aws.webhook.webhook_processors.ec2_instance_webhook_processor import (
    Ec2InstanceWebhookProcessor,
)
from aws.webhook.webhook_processors.ecs_service_webhook_processor import (
    EcsServiceWebhookProcessor,
)
from aws.webhook.webhook_processors.lambda_function_webhook_processor import (
    LambdaFunctionWebhookProcessor,
)
from aws.webhook.webhook_processors.s3_bucket_webhook_processor import (
    S3BucketWebhookProcessor,
)
from aws.webhook.webhook_processors.webhook_healthcheck_processor import (
    WebhookHealthcheckProcessor,
)


WEBHOOK_PATH = "/webhook/live-events"


def register_live_events_webhooks() -> None:
    """Wire up the AWS-V3 live-events endpoint.

    Called once from `main.py` at module load time so the FastAPI app
    has the middleware attached before it starts serving, and the
    framework router has every processor registered before any
    request arrives.
    """
    full_path = f"{ocean.app.route_prefix}/integration{WEBHOOK_PATH}"
    register_live_events_auth_middleware(full_path)

    ocean.add_webhook_processor(WEBHOOK_PATH, WebhookHealthcheckProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, Ec2InstanceWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, EcsServiceWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, LambdaFunctionWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, S3BucketWebhookProcessor)
