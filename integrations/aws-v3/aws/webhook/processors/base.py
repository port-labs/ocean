from __future__ import annotations

import json
from abc import abstractmethod
from typing import Any, ClassVar

from aiobotocore.session import AioSession
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
from port_ocean.exceptions.webhook_processor import RetryableError

from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel

from aws.webhook.events import (
    PORT_HMAC_HEADER,
    SNS_MESSAGE_TYPE_HEADER,
    SnsMessageType,
)
from aws.webhook.idempotency import InMemoryIdempotencyStore
from aws.webhook.session_resolver import AccountSessionResolver
from aws.webhook.signature import HmacSignatureVerifier, SnsSignatureVerifier


# Module-level singletons so every processor instance (Ocean creates one
# per inbound POST) shares the same dedup table, session cache, and
# SNS-cert cache. Lazy on first use because ocean.integration_config
# isn't loaded until startup completes.
_idempotency_store: InMemoryIdempotencyStore | None = None
_session_resolver: AccountSessionResolver | None = None
_sns_verifier: SnsSignatureVerifier | None = None


def _get_idempotency_store() -> InMemoryIdempotencyStore:
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = InMemoryIdempotencyStore()
    return _idempotency_store


def _get_session_resolver() -> AccountSessionResolver:
    global _session_resolver
    if _session_resolver is None:
        _session_resolver = AccountSessionResolver()
    return _session_resolver


def _get_sns_verifier() -> SnsSignatureVerifier:
    global _sns_verifier
    if _sns_verifier is None:
        config = ocean.integration_config
        raw = config.get("sns_cert_host_allowlist") or "sns.amazonaws.com"
        suffixes = tuple(s.strip() for s in raw.split(",") if s.strip())
        _sns_verifier = SnsSignatureVerifier(allowed_host_suffixes=suffixes)
    return _sns_verifier


def _reset_singletons_for_tests() -> None:
    """Reset module-level singletons (only intended for tests)."""
    global _idempotency_store, _session_resolver, _sns_verifier
    _idempotency_store = None
    _session_resolver = None
    _sns_verifier = None


class AWSLiveEventProcessor(AbstractWebhookProcessor):
    """Template-method base for per-kind AWS event handlers.

    The HTTPS endpoint receives an SNS envelope; the actual EventBridge
    event is the JSON string in `Message`. `_eventbridge_envelope`
    unwraps it once and passes the resulting dict to subclass hooks.

    Subclasses override the class-level metadata fields and the
    instance hooks below.
    """

    # ---- subclass-supplied metadata --------------------------------

    kind: ClassVar[str] = ""
    detail_types: ClassVar[frozenset[str]] = frozenset()
    # For CloudTrail-via-EventBridge, narrow further by `detail.eventSource`.
    # Empty = match any source under the listed detail-types.
    event_sources: ClassVar[frozenset[str]] = frozenset()
    exporter_cls: ClassVar[type[IResourceExporter] | None] = None

    # ---- subclass-supplied behavior --------------------------------

    @abstractmethod
    def extract_identifier(self, envelope: dict[str, Any]) -> dict[str, Any] | None:
        """Pull the natural-key fields out of the EventBridge envelope.

        The envelope is the full dict (`detail`, `resources`, etc.).
        Subclasses pick from `envelope["detail"]` or `envelope["resources"]`
        as appropriate. Return `None` to skip a malformed event.
        """

    @abstractmethod
    def is_delete(self, envelope: dict[str, Any]) -> bool:
        """True iff this event represents a deletion of the resource."""

    @abstractmethod
    def build_request(
        self,
        identifier: dict[str, Any],
        account_id: str,
        region: str,
        include: list[str],
    ) -> ResourceRequestModel:
        """Build the exporter's `SingleXRequest` from the identifier."""

    def deleted_entity_payload(
        self,
        identifier: dict[str, Any],
        account_id: str,
        region: str,
    ) -> dict[str, Any]:
        """Delete payload sent to Port. Default shape fits most kinds."""
        return {
            "Type": self.kind,
            "Properties": identifier,
            "__ExtraContext": {"AccountId": account_id, "Region": region},
        }

    # ---- framework hooks -------------------------------------------

    async def authenticate(
        self, payload: EventPayload, headers: EventHeaders
    ) -> bool:
        # SNS signature is always required. HMAC layers on top when a
        # webhookSecret is configured.
        msg_type = headers.get(SNS_MESSAGE_TYPE_HEADER)
        if msg_type not in {
            SnsMessageType.NOTIFICATION.value,
            SnsMessageType.SUBSCRIPTION_CONFIRMATION.value,
            SnsMessageType.UNSUBSCRIBE_CONFIRMATION.value,
        }:
            logger.warning(
                "AWS live-event auth: rejected (missing/unknown SNS message type)",
                extra={"outcome": "rejected_message_type"},
            )
            return False

        verifier = _get_sns_verifier()
        if not await verifier.verify(payload):
            logger.warning(
                "AWS live-event auth: rejected SNS signature",
                extra={"outcome": "rejected_signature"},
            )
            return False

        secret = self._configured_webhook_secret()
        if secret:
            raw_body = self._raw_body_or_reserialize(payload)
            hmac_verifier = HmacSignatureVerifier(secret)
            if not hmac_verifier.verify(raw_body, headers.get(PORT_HMAC_HEADER)):
                logger.warning(
                    "AWS live-event auth: rejected HMAC",
                    extra={"outcome": "rejected_hmac"},
                )
                return False
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return isinstance(payload, dict) and "Type" in payload

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not self._live_events_enabled():
            logger.info(
                "AWS live-event skipped — liveEventsEnabled=false",
                extra={"outcome": "skipped_disabled"},
            )
            return False

        msg_type = event.headers.get(SNS_MESSAGE_TYPE_HEADER)
        # SubscriptionConfirmation/UnsubscribeConfirmation route to
        # SnsSubscriptionConfirmationProcessor.
        if msg_type != SnsMessageType.NOTIFICATION.value:
            return False

        envelope = self._eventbridge_envelope(event.payload)
        if envelope is None:
            return False

        if envelope.get("detail-type") not in self.detail_types:
            return False

        if self.event_sources:
            event_source = envelope.get("detail", {}).get("eventSource")
            if event_source not in self.event_sources:
                return False

        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [self.kind] if self.kind else []

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        envelope = self._eventbridge_envelope(payload) or {}
        detail = envelope.get("detail", {}) or {}
        account_id = str(envelope.get("account") or detail.get("account") or "")
        region = str(envelope.get("region") or detail.get("awsRegion") or "")
        detail_type = envelope.get("detail-type", "")
        log_ctx = {
            "kind": self.kind,
            "account_id": account_id,
            "region": region,
            "detail_type": detail_type,
        }

        # Dedup on SNS MessageId from the outer envelope.
        message_id = payload.get("MessageId") or ""
        if await _get_idempotency_store().seen_or_record(message_id):
            logger.info(
                "AWS live-event skipped — duplicate MessageId",
                extra={**log_ctx, "outcome": "skipped_duplicate"},
            )
            return WebhookEventRawResults([], [])

        identifier = self.extract_identifier(envelope)
        if identifier is None:
            logger.info(
                "AWS live-event skipped — no identifier",
                extra={**log_ctx, "outcome": "skipped_no_identifier"},
            )
            return WebhookEventRawResults([], [])

        if not account_id or not region:
            logger.warning(
                "AWS live-event skipped — missing account/region",
                extra={**log_ctx, "outcome": "skipped_missing_envelope"},
            )
            return WebhookEventRawResults([], [])

        if self.is_delete(envelope):
            logger.info(
                "AWS live-event delete",
                extra={**log_ctx, "outcome": "deleted"},
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    self.deleted_entity_payload(identifier, account_id, region)
                ],
            )

        session = await _get_session_resolver().get(account_id)
        if session is None:
            logger.warning(
                "AWS live-event skipped — unknown account",
                extra={**log_ctx, "outcome": "skipped_unknown_account"},
            )
            return WebhookEventRawResults([], [])

        include = self._include_actions(resource)
        request = self.build_request(identifier, account_id, region, include)
        entity = await self._fetch_with_retry(session, request, log_ctx, identifier)
        if entity is None:
            # 404 from AWS — emit a delete so the catalog stays in sync
            # with reality even if the resource vanished mid-flight.
            logger.info(
                "AWS live-event delete (resource gone in AWS)",
                extra={**log_ctx, "outcome": "delete_on_404"},
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    self.deleted_entity_payload(identifier, account_id, region)
                ],
            )

        logger.info(
            "AWS live-event upsert",
            extra={**log_ctx, "outcome": "upserted"},
        )
        return WebhookEventRawResults(
            updated_raw_results=[entity],
            deleted_raw_results=[],
        )

    # ---- helpers ---------------------------------------------------

    @staticmethod
    def _eventbridge_envelope(payload: EventPayload) -> dict[str, Any] | None:
        """Pull the EventBridge envelope out of an SNS notification body.

        SNS wraps the EventBridge event in `Message` as a JSON string.
        For raw delivery (direct EventBridge → HTTPS, no SNS in between)
        the envelope already sits at the top level.
        """
        message = payload.get("Message")
        if isinstance(message, str):
            try:
                parsed = json.loads(message)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        if "detail-type" in payload:
            return payload
        return None

    @staticmethod
    def _configured_webhook_secret() -> str | None:
        secret = ocean.integration_config.get("webhook_secret")
        if isinstance(secret, str) and secret:
            return secret
        return None

    @staticmethod
    def _live_events_enabled() -> bool:
        cfg = ocean.integration_config
        value = cfg.get("live_events_enabled")
        if value is None:
            return True
        if isinstance(value, bool):
            return value
        return str(value).lower() not in {"false", "0", "no"}

    @staticmethod
    def _raw_body_or_reserialize(payload: EventPayload) -> bytes:
        # Ocean parses the body before this layer sees it. For HMAC
        # verification, re-serialise in the same canonical form the
        # EventBridge InputTransformer uses: compact JSON, sorted keys.
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )

    @staticmethod
    def _include_actions(resource: ResourceConfig | None) -> list[str]:
        if resource is None:
            return []
        selector = getattr(resource, "selector", None)
        return list(getattr(selector, "include_actions", []) or [])

    async def _fetch_with_retry(
        self,
        session: AioSession,
        request: ResourceRequestModel,
        log_ctx: dict[str, Any],
        identifier: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self.exporter_cls is None:
            raise RuntimeError(
                f"{type(self).__name__}.exporter_cls is not set"
            )
        exporter = self.exporter_cls(session)
        try:
            entity = await exporter.get_resource(request)
        except Exception as exc:
            if self._is_not_found(exc):
                return None
            if self._is_throttling(exc):
                logger.warning(
                    "AWS live-event throttled, will retry",
                    extra={**log_ctx, "outcome": "error_retryable"},
                )
                raise RetryableError(str(exc)) from exc
            logger.exception(
                "AWS live-event fetch failed",
                extra={**log_ctx, "outcome": "error_fatal"},
            )
            raise
        return entity or None

    @staticmethod
    def _error_code(exc: Exception) -> str:
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return ""
        error = response.get("Error")
        if not isinstance(error, dict):
            return ""
        return str(error.get("Code", ""))

    @classmethod
    def _is_not_found(cls, exc: Exception) -> bool:
        return cls._error_code(exc) in {
            "ResourceNotFoundException",
            "NoSuchBucket",
            "InvalidInstanceID.NotFound",
            "ServiceNotFoundException",
            "ClusterNotFoundException",
            "404",
        }

    @classmethod
    def _is_throttling(cls, exc: Exception) -> bool:
        return cls._error_code(exc) in {
            "ThrottlingException",
            "Throttling",
            "TooManyRequestsException",
            "RequestLimitExceeded",
        }


__all__ = [
    "AWSLiveEventProcessor",
    "_get_idempotency_store",
    "_get_session_resolver",
    "_get_sns_verifier",
    "_reset_singletons_for_tests",
]
