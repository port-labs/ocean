import logging
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

class BitbucketWebhook(WebhookEvent):
    async def handle_event(self, event):
        logging.info(f"Webhook event received: {event}")
