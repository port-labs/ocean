from port_ocean.context.ocean import ocean

from langfuse.webhook.webhook_processors.prompt_webhook_processor import (
    PromptWebhookProcessor,
)

WEBHOOK_PATH = "/webhook"


def register_live_events_webhooks() -> None:
    ocean.add_webhook_processor(WEBHOOK_PATH, PromptWebhookProcessor)
