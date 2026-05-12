"""Register AWS live-event webhook processors with Ocean.

Same pattern as ``integrations/github/github/webhook/registry.py``: one
registration function, one route. ``main.py`` imports
``register_live_events_webhooks`` and invokes it at import time.
"""

from port_ocean.context.ocean import ocean

from aws.webhook.processors.ec2_instance_processor import (
    EC2InstanceWebhookProcessor,
)
from aws.webhook.processors.ecs_service_processor import (
    EcsServiceWebhookProcessor,
)
from aws.webhook.processors.lambda_function_processor import (
    LambdaFunctionWebhookProcessor,
)
from aws.webhook.processors.s3_bucket_processor import (
    S3BucketWebhookProcessor,
)


WEBHOOK_PATH: str = "/webhook"
"""Single ingress path for all AWS live events.

Ocean mounts this under the integration prefix, yielding e.g.
``POST /integration/webhook`` from the customer's perspective.
"""


def register_live_events_webhooks() -> None:
    """Register all AWS live-event processors against :data:`WEBHOOK_PATH`.

    Each processor's `should_process_event` picks matching events; registration
    order does not matter for correctness.
    """

    ocean.add_webhook_processor(WEBHOOK_PATH, EC2InstanceWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, EcsServiceWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, LambdaFunctionWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, S3BucketWebhookProcessor)


__all__ = [
    "WEBHOOK_PATH",
    "ocean",
    "register_live_events_webhooks",
]
