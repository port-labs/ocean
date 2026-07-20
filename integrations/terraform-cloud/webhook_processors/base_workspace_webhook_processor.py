from webhook_processors.terraform_base_webhook_processor import (
    TerraformBaseWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from client import WorkspaceRunEvents


class BaseWorkspaceWebhookProcessor(TerraformBaseWebhookProcessor):
    """should focus on only workspace run events"""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if notifications := event.payload.get("notifications", []):
            for notification in notifications:
                run_status = notification["run_status"]
                trigger = notification["trigger"]
                try:
                    # Only process state when run has applied changes
                    if run_status == "applied" and bool(WorkspaceRunEvents(trigger)):
                        return True
                except (KeyError, ValueError):
                    continue
        return False
