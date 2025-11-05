import hashlib
import hmac

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class TerraformBaseWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    def _is_verification_event(self, payload: EventPayload) -> bool:
        """Check if this is a Terraform Cloud webhook verification event."""
        try:
            notifications = payload["notifications"]
            if isinstance(notifications, list) and len(notifications) > 0:
                first_notification = notifications[0]
                if isinstance(first_notification, dict):
                    return first_notification["trigger"] == "verification"
        except (KeyError, TypeError):
            pass
        return False

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if notifications := event.payload.get("notifications", []):
            trigger = notifications[0].get("trigger") if notifications else "unknown"
            logger.info(f"Received Terraform webhook with trigger: {trigger}")

        # Skip processing verification events - they're handled by responding with 200 OK
        if self._is_verification_event(event.payload):
            logger.info(
                "Terraform Cloud webhook verification event received - skipping processing"
            )
            return False

        # Verify HMAC signature if webhook_secret is configured
        webhook_secret = ocean.integration_config.get("webhook_secret")

        if not webhook_secret:
            logger.warning(
                "No webhook_secret configured for Terraform Cloud webhooks; accepting event without signature validation. "
            )
            return True

        if event._original_request is None:
            logger.error("Unable to verify webhook signature: request body unavailable")
            return False

        signature = event.headers.get("x-tfe-notification-signature", "")
        if not signature:
            logger.error(
                "Missing 'x-tfe-notification-signature' header. Webhook authentication failed."
            )
            return False

        # Compute HMAC using SHA-512
        body = await event._original_request.body()
        hmac_obj = hmac.new(
            webhook_secret.encode("utf-8"),
            body,
            hashlib.sha512,
        )
        expected_signature = hmac_obj.hexdigest()

        # Constant-time comparison
        if not hmac.compare_digest(signature, expected_signature):
            logger.error("Webhook signature validation failed")
            return False

        logger.info("Webhook signature validated successfully")
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that payload has the required Terraform webhook structure."""
        if not isinstance(payload, dict):
            return False

        # Validate notifications array exists and has content
        notifications = payload.get("notifications")
        if not isinstance(notifications, list) or len(notifications) == 0:
            logger.error("Webhook payload missing required 'notifications' array")
            return False

        # Validate notification structure
        first_notification = notifications[0]
        if not isinstance(first_notification, dict):
            logger.error("Invalid notification structure")
            return False

        if "trigger" not in first_notification:
            logger.error("Webhook notification missing required 'trigger' field")
            return False

        if "run_status" not in first_notification:
            logger.error("Webhook notification missing required 'run_status' field")
            return False

        # Validate root level fields
        if "run_id" not in payload:
            logger.error("Webhook payload missing required 'run_id' field")
            return False

        if "workspace_id" not in payload:
            logger.error("Webhook payload missing required 'workspace_id' field")
            return False

        return True
