from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from webhook_processors.terraform_base_webhook_processor import (
    TerraformBaseWebhookProcessor,
)


class BaseStateWebhookProcessor(TerraformBaseWebhookProcessor):
    """base processor for state file and state version webhook processors"""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if notifications := event.payload.get("notifications", []):
            for notification in notifications:
                run_status = notification["run_status"]
                # Only process state when run has applied changes
                if run_status == "applied":
                    return True
        return False
