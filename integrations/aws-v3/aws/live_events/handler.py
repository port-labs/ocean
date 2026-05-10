import base64
import hashlib
import hmac
import json
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from aws.auth.session_factory import get_all_account_sessions
from aws.live_events.processors.base import BaseLiveEventProcessor
from aws.live_events.processors.ec2 import EC2LiveEventProcessor
from aws.live_events.processors.ecs_service import EcsServiceLiveEventProcessor
from aws.live_events.processors.aws_lambda import LambdaLiveEventProcessor
from aws.live_events.processors.s3 import S3LiveEventProcessor

# Ordered list of all registered per-kind processors.
_PROCESSORS: list[BaseLiveEventProcessor] = [
    EC2LiveEventProcessor(),
    EcsServiceLiveEventProcessor(),
    LambdaLiveEventProcessor(),
    S3LiveEventProcessor(),
]

_SNS_SIGNATURE_HASHERS: dict[str, type[hashes.HashAlgorithm]] = {
    "1": hashes.SHA1,
    "2": hashes.SHA256,
}


def _get_processor(
    detail_type: str, detail: dict[str, Any]
) -> BaseLiveEventProcessor | None:
    """Return the first processor that can handle this detail-type + detail combination."""
    for processor in _PROCESSORS:
        if processor.can_handle(detail_type, detail):
            return processor
    return None


def _parse_sns_message(payload: EventPayload) -> dict[str, Any] | None:
    """Unwrap the EventBridge event from the SNS notification envelope.

    Returns the parsed EventBridge event dict, or None on failure.
    """
    raw_message = payload.get("Message")
    if not raw_message:
        return None
    try:
        return json.loads(raw_message)
    except (json.JSONDecodeError, TypeError):
        return None


def _build_sns_string_to_sign(payload: EventPayload) -> str:
    """Build the canonical SNS string-to-sign for certificate validation."""

    fields: list[str] = []

    def add(field_name: str) -> None:
        value = payload.get(field_name)
        if value not in (None, ""):
            fields.extend([field_name, str(value)])

    sns_type = payload.get("Type")
    if sns_type == "Notification":
        add("Message")
        add("MessageId")
        add("Subject")
        add("Timestamp")
        add("TopicArn")
        add("Type")
    elif sns_type in {"SubscriptionConfirmation", "UnsubscribeConfirmation"}:
        add("Message")
        add("MessageId")
        add("SubscribeURL")
        add("Timestamp")
        add("Token")
        add("TopicArn")
        add("Type")
    else:
        raise ValueError(f"Unsupported SNS message type '{sns_type}'")

    return "\n".join(fields) + "\n"


def _is_valid_sns_signing_cert_url(cert_url: str) -> bool:
    """Allow only AWS SNS HTTPS certificate endpoints."""

    try:
        parsed = urlparse(cert_url)
    except ValueError:
        return False

    host = parsed.hostname or ""
    return (
        parsed.scheme == "https"
        and host.startswith("sns.")
        and host.endswith(".amazonaws.com")
        and parsed.path.endswith(".pem")
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


@lru_cache(maxsize=16)
def _load_sns_signing_certificate(cert_url: str) -> x509.Certificate:
    if not _is_valid_sns_signing_cert_url(cert_url):
        raise ValueError("Invalid SNS SigningCertURL")

    with urlopen(cert_url, timeout=5) as response:
        cert_pem = response.read()

    return x509.load_pem_x509_certificate(cert_pem)


class AWSWebhookProcessor(AbstractWebhookProcessor):
    """Webhook processor for AWS live events delivered via SNS → Ocean HTTPS.

    Expected request body format:
        An SNS notification envelope (JSON) where the ``Message`` field is a
        JSON-encoded EventBridge event.

    Signature validation:
        When ``webhook_secret`` is configured in the integration config, every
        POST must include an ``x-hub-signature-256`` header whose value is
        ``sha256=<HMAC-SHA256(raw_body, webhook_secret)>``. Requests with missing
        or invalid signatures are rejected.
    """

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # Signature verification requires the raw request body, which is only
        # accessible via event._original_request (available in should_process_event).
        # This method intentionally delegates to should_process_event.
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        sns_type = payload.get("Type")
        if not sns_type:
            logger.warning(
                "Received request without SNS 'Type' field — rejecting",
                extra={"reason": "missing_sns_type"},
            )
            return False
        if sns_type == "SubscriptionConfirmation":
            # Subscription confirmation events don't carry a Message body; they
            # are valid but will not produce any entity updates.
            return True
        if sns_type != "Notification":
            logger.warning(
                f"Unsupported SNS message type '{sns_type}' — rejecting",
                extra={"sns_type": sns_type, "reason": "unsupported_type"},
            )
            return False
        return "Message" in payload

    async def should_process_event(self, event: WebhookEvent) -> bool:

        if not await self._verify_signature(event):
            return False

        payload = event.payload
        sns_type: str = payload.get("Type", "")

        if sns_type == "SubscriptionConfirmation":
            logger.info(
                "Received SNS SubscriptionConfirmation — acknowledging",
                extra={"TopicArn": payload.get("TopicArn")},
            )
            return False

        if sns_type != "Notification":
            logger.info(
                f"Skipping SNS message type '{sns_type}'",
                extra={"sns_type": sns_type, "reason": "not_notification"},
            )
            return False

        message = _parse_sns_message(payload)
        if message is None:
            logger.warning(
                "Failed to parse SNS Message as EventBridge JSON — skipping",
                extra={"reason": "parse_error"},
            )
            return False

        detail_type: str = message.get("detail-type", "")
        detail: dict[str, Any] = message.get("detail", {})

        if _get_processor(detail_type, detail) is None:
            logger.info(
                f"No handler registered for detail-type '{detail_type}' — skipping",
                extra={
                    "detail_type": detail_type,
                    "reason": "no_handler",
                },
            )
            return False

        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        message = _parse_sns_message(event.payload)
        if message is None:
            return []
        detail_type: str = message.get("detail-type", "")
        detail: dict[str, Any] = message.get("detail", {})
        processor = _get_processor(detail_type, detail)
        if processor is None:
            return []
        return processor.kinds

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        message = _parse_sns_message(payload)
        if message is None:
            logger.error(
                "handle_event called with unparseable SNS Message",
                extra={"outcome": "error"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        detail_type: str = message.get("detail-type", "")
        detail: dict[str, Any] = message.get("detail", {})
        account_id: str = message.get("account", "")
        region: str = message.get("region", "")

        logger.info(
            "Received live event",
            extra={
                "kind": resource.kind,
                "detail_type": detail_type,
                "account": account_id,
                "region": region,
            },
        )

        processor = _get_processor(detail_type, detail)
        if processor is None:
            logger.warning(
                f"No processor found for detail-type '{detail_type}' in handle_event",
                extra={"kind": resource.kind, "reason": "no_processor"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


        target_session = None
        async for account_info, session in get_all_account_sessions():
            if account_info["Id"] == account_id:
                target_session = session
                break

        if target_session is None:
            logger.error(
                f"No configured AWS session found for account '{account_id}' — "
                "ensure the account is in the integration's account configuration",
                extra={"account": account_id, "kind": resource.kind, "outcome": "error"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        try:
            result = await processor.handle(
                event=message,
                account_id=account_id,
                region=region,
                session=target_session,
            )
        except Exception as exc:
            logger.error(
                f"Unhandled error in processor for {resource.kind}: {exc}",
                extra={
                    "kind": resource.kind,
                    "account": account_id,
                    "region": region,
                    "outcome": "error",
                },
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        logger.info(
            "Live event processed",
            extra={
                "kind": resource.kind,
                "detail_type": detail_type,
                "account": account_id,
                "region": region,
                "updated": len(result.updated_raw_results),
                "deleted": len(result.deleted_raw_results),
                "outcome": "success",
            },
        )
        return result


    async def _verify_signature(self, event: WebhookEvent) -> bool:
        """Validate either HMAC or native SNS signatures.

        When ``webhook_secret`` is configured, the request must carry
        ``x-hub-signature-256`` whose value is
        ``sha256=<HMAC-SHA256(raw_body, webhook_secret)>``.

        When no secret is configured, the request is treated as a direct SNS
        delivery and validated using the SNS X.509 certificate signature fields
        embedded in the payload.
        """
        secret: str | None = ocean.integration_config.get(
            "webhook_secret"
        ) or ocean.integration_config.get("webhookSecret")

        if secret:
            return await self._verify_hmac_signature(event, secret)

        return self._verify_sns_signature(event.payload)

    async def _verify_hmac_signature(self, event: WebhookEvent, secret: str) -> bool:
        """Validate the HMAC-SHA256 signature for forwarded webhook requests."""

        if event._original_request is None:
            # No raw request available (e.g. replayed from queue); skip.
            logger.debug(
                "No original request available for HMAC verification — allowing",
                extra={"outcome": "skipped", "verification": "hmac"},
            )
            return True

        signature: str = event.headers.get("x-hub-signature-256", "")
        if not signature:
            logger.error(
                "Missing 'x-hub-signature-256' header — rejecting request",
                extra={"outcome": "rejected", "verification": "hmac"},
            )
            return False

        raw_body: bytes = await event._original_request.body()
        computed = "sha256=" + hmac.new(
            secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(signature, computed):
            logger.debug(
                "HMAC signature validation passed",
                extra={"outcome": "accepted", "verification": "hmac"},
            )
            return True

        logger.error(
            "HMAC signature validation failed — mismatch",
            extra={"outcome": "rejected", "verification": "hmac"},
        )
        return False

    def _verify_sns_signature(self, payload: EventPayload) -> bool:
        """Validate the native SNS payload signature for direct HTTPS deliveries."""

        signature_version = str(payload.get("SignatureVersion", ""))
        signature_value = payload.get("Signature")
        signing_cert_url = str(payload.get("SigningCertURL", ""))

        if not signature_value or not signing_cert_url:
            logger.error(
                "Missing SNS signature fields — rejecting request",
                extra={"outcome": "rejected", "verification": "sns"},
            )
            return False

        hash_algorithm = _SNS_SIGNATURE_HASHERS.get(signature_version)
        if hash_algorithm is None:
            logger.error(
                f"Unsupported SNS SignatureVersion '{signature_version}' — rejecting request",
                extra={"outcome": "rejected", "verification": "sns"},
            )
            return False

        try:
            certificate = _load_sns_signing_certificate(signing_cert_url)
            string_to_sign = _build_sns_string_to_sign(payload).encode("utf-8")
            decoded_signature = base64.b64decode(signature_value, validate=True)
            certificate.public_key().verify(
                decoded_signature,
                string_to_sign,
                padding.PKCS1v15(),
                hash_algorithm(),
            )
        except (InvalidSignature, ValueError, TypeError, OSError) as exc:
            logger.error(
                f"SNS signature validation failed — rejecting request: {exc}",
                extra={"outcome": "rejected", "verification": "sns"},
            )
            return False

        logger.debug(
            "SNS signature validation passed",
            extra={"outcome": "accepted", "verification": "sns"},
        )
        return True
