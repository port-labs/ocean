from typing import Any, cast
from loguru import logger

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    EventHeaders,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from aws.core.helpers.types import ObjectKind
from aws.events.dedupe import InMemoryDeduper
import json
import hmac
import hashlib

from .handlers.ec2 import EC2EventHandler
from .handlers.ecs_service import EcsServiceEventHandler
from .handlers.lambda_fn import LambdaEventHandler
from .handlers.s3 import S3EventHandler


class AWSEventWebhookProcessor(AbstractWebhookProcessor):
    """Processor that routes EventBridge/SNS events to per-kind handlers."""

    _deduper = InMemoryDeduper()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # Expect port_ocean to pass the configured secret in resource config (webhookSecret)
        # If the incoming message is an SNS envelope, we've already unwrapped it in before_processing
        secret = None
        try:
            if getattr(self.event, "resource_config", None):
                # resource_config is a Port ResourceConfig object in production; tests may set a simple object
                raw = getattr(self.event.resource_config, "raw_config", None)
                if isinstance(raw, dict):
                    secret = raw.get("webhookSecret")
        except Exception:
            secret = None

        if not secret:
            logger.warning("No webhookSecret configured for AWS integration; rejecting live event")
            return False

        # SNS sets header 'X-Amz-Sns-Signature' or EventBridge may not sign; we'll accept a simple HMAC header 'X-AWS-Signature'
        signature = headers.get("X-AWS-Signature") or headers.get("X-Amz-Sns-Signature")
        if not signature:
            logger.warning("Missing signature header")
            return False

        # compute HMAC over canonical raw_body
        try:
            computed = hmac.new(secret.encode(), (self.event.raw_body or "").encode(), hashlib.sha256).hexdigest()
            valid = hmac.compare_digest(computed, signature)
            logger.info(f"Signature validation result: {valid}")
            return valid
        except Exception as e:
            logger.error(f"Error computing signature: {e}")
            return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        # basic validation
        return isinstance(payload, dict) and ("detail-type" in payload or "detail" in payload)

    async def should_process_event(self, event: WebhookEvent) -> bool:
        # We accept EventBridge and SNS-wrapped EventBridge events
        payload = event.payload
        return bool(payload and (payload.get("source") or payload.get("detail-type")))

    async def before_processing(self) -> None:
        """Called before processing — normalize SNS envelopes and dedupe by MessageId."""
        # If SNS envelope: it will have 'Type' and 'Message' fields and possibly MessageId
        try:
            raw_body = getattr(self.event, "raw_body", "") or ""
            # If payload looks like SNS (has 'Type' and 'Message'), parse inner message
            payload = self.event.payload or {}
            if isinstance(payload, dict) and payload.get("Type") and payload.get("Message"):
                # SNS wraps the actual message as a JSON string in Message
                inner = payload.get("Message")
                try:
                    inner_json = json.loads(inner)
                except Exception:
                    inner_json = inner

                # replace event.payload with inner (if parsed)
                self.event.payload = inner_json
                # raw_body should be the inner JSON string for signature validation
                if isinstance(inner_json, (dict, list)):
                    self.event.raw_body = json.dumps(inner_json, separators=(",", ":"))
                else:
                    self.event.raw_body = str(inner)

                # dedupe using MessageId if present
                msg_id = payload.get("MessageId")
                if msg_id:
                    if self._deduper.contains(msg_id):
                        # mark cancelled by setting a flag; AbstractWebhookProcessor may not have explicit cancellation
                        logger.info(f"Duplicate message detected {msg_id}; skipping processing")
                        # We set an attribute so handle_event can decide to skip
                        self.event._skip_processing = True
                        return
                    else:
                        self._deduper.add(msg_id)

            # default raw_body if not set
            if not getattr(self.event, "raw_body", None):
                self.event.raw_body = raw_body
        except Exception as e:
            logger.debug(f"Error during before_processing normalization: {e}")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        detail_type = event.payload.get("detail-type", "")
        # map to kinds
        if "EC2 Instance State-change Notification" in detail_type:
            return [ObjectKind.EC2_INSTANCE]
        if event.payload.get("source") == "aws.ecs" or "ECS" in detail_type:
            return [ObjectKind.ECS_SERVICE]
        if event.payload.get("source") == "aws.lambda" or "Lambda" in detail_type:
            return [ObjectKind.LAMBDA_FUNCTION]
        if event.payload.get("source") == "aws.s3" or "S3" in detail_type:
            return [ObjectKind.S3_BUCKET]
        # fallback: empty list
        return []

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        # If dedupe marked this event as duplicate, skip handling
        if getattr(self.event, "_skip_processing", False):
            logger.info("Skipping duplicate event processing")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
        # Dispatch by detail-type / source
        kind = (await self.get_matching_kinds(self.event))
        detail_type = payload.get("detail-type", "")
        logger.info(f"Dispatching AWS event {detail_type} -> kinds {kind}")

        # choose handler per first kind
        if not kind:
            logger.warning("No matching kind for event; skipping")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        k = kind[0]
        if k == ObjectKind.EC2_INSTANCE:
            handler = EC2EventHandler(self.event)
            return await handler.handle(payload, resource)
        if k == ObjectKind.ECS_SERVICE:
            handler = EcsServiceEventHandler(self.event)
            return await handler.handle(payload, resource)
        if k == ObjectKind.LAMBDA_FUNCTION:
            handler = LambdaEventHandler(self.event)
            return await handler.handle(payload, resource)
        if k == ObjectKind.S3_BUCKET:
            handler = S3EventHandler(self.event)
            return await handler.handle(payload, resource)

        logger.warning(f"Unhandled kind {k}")
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
