"""
Live events webhook processor.

Registered with Ocean as a webhook handler. Ocean exposes it at:
  POST /integration/live-events/webhook

Flow:
  1. Validate the SNS signature on the raw request body.
  2. If the message type is SubscriptionConfirmation, auto-confirm the SNS
     subscription by fetching the SubscribeURL (required once per topic).
  3. For Notification messages, route the inner EventBridge event to the
     correct per-kind handler.

SNS sends a raw JSON body (not form-encoded), so we read the raw bytes and
parse ourselves.
"""

import json
from typing import Any

import aiohttp
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    WebhookEvent,
    WebhookEventRawResults,
)

from aws.auth.session_factory import get_all_account_sessions
from aws.live_events.webhook.router import route_sns_notification
from aws.live_events.webhook.validator import validate_sns_signature


class LiveEventsWebhookProcessor(AbstractWebhookProcessor):
    """
    Handles inbound SNS notifications carrying EventBridge live events.

    SNS sends one HTTP POST per event. The body is a JSON object with:
      - Type: "Notification" | "SubscriptionConfirmation"
      - Message: JSON string containing the EventBridge event (for Notifications)
      - Signature, SigningCertURL: used for validation
    """

    async def authenticate(self, payload: dict[str, Any], headers: EventHeaders) -> bool:
        # Signature validation happens inside `should_process_event` where we
        # have access to the raw body. Here we always return True and let the
        # processor raise an exception on bad signatures instead.
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        # We validate the signature here using the raw body bytes.
        raw_body: bytes = event.body if isinstance(event.body, bytes) else event.body.encode()
        try:
            await validate_sns_signature(raw_body)
            return True
        except ValueError as exc:
            logger.warning(f"[webhook] rejected request — signature invalid: {exc}")
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        # Kinds are resolved per-event inside handle_event based on the
        # EventBridge detail-type. Returning an empty list here is fine —
        # we register entities directly in handle_event.
        return []

    async def handle_event(
        self, payload: dict[str, Any], resource_config: Any
    ) -> WebhookEventRawResults:
        msg_type: str = payload.get("Type", "")

        if msg_type == "SubscriptionConfirmation":
            await self._confirm_subscription(payload)
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if msg_type != "Notification":
            logger.info(f"[webhook] ignoring SNS message type {msg_type!r}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Resolve an AWS session for the account that sent the event.
        # The account_id is inside the EventBridge envelope (inside Message).
        raw_message: str = payload.get("Message", "")
        try:
            event_envelope = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.error("[webhook] could not parse SNS Message as JSON")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        target_account: str = event_envelope.get("account", "")

        session = None
        async for account, acct_session in get_all_account_sessions():
            if account.get("Id") == target_account:
                session = acct_session
                break

        if session is None:
            logger.warning(
                f"[webhook] no session found for account {target_account!r}, "
                "using default session from first available account"
            )
            async for _, acct_session in get_all_account_sessions():
                session = acct_session
                break

        if session is None:
            logger.error("[webhook] no AWS sessions available, cannot process event")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        await route_sns_notification(payload, session)

        # Entity registration is done inside the handlers via ocean.register_raw /
        # ocean.unregister_raw. We return empty results here.
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def _confirm_subscription(self, payload: dict[str, Any]) -> None:
        """
        Auto-confirm the SNS → Ocean HTTPS subscription.

        SNS sends a SubscriptionConfirmation when the topic first subscribes
        to our endpoint. We must fetch the SubscribeURL to activate delivery.
        """
        subscribe_url: str = payload.get("SubscribeURL", "")
        if not subscribe_url:
            logger.error("[webhook] SubscriptionConfirmation missing SubscribeURL")
            return

        logger.info(f"[webhook] confirming SNS subscription via {subscribe_url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    subscribe_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    resp.raise_for_status()
                    logger.info("[webhook] SNS subscription confirmed successfully")
        except Exception as exc:
            logger.error(f"[webhook] failed to confirm SNS subscription: {exc}")
