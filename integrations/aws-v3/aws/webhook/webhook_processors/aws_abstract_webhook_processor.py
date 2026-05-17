"""Abstract base for all AWS-V3 live-event webhook processors.

Each concrete processor handles a single AWS resource kind (EC2 instance,
ECS service, Lambda function, S3 bucket). The base class implements the
shared contract:

  - `authenticate()`        constant-time bearer compare, defense-in-depth
                            against a missing/broken middleware.
  - `validate_payload()`    enforces the EventBridge envelope shape.
  - `should_process_event()`enforces the `allowedAccountIds` allowlist.

Concrete subclasses implement `_matches_event()`, `get_matching_kinds()`
and `handle_event()`, which applies `AWSResourceSelector.regionPolicy`
to the workload region (`payload["region"]` or, for S3, the resolved
bucket home region).
"""

from __future__ import annotations

import hmac
from abc import abstractmethod
from typing import Any, cast

from loguru import logger

from integration import AWSResourceConfig
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


_REQUIRED_ENVELOPE_FIELDS: tuple[str, ...] = (
    "source",
    "detail-type",
    "detail",
    "account",
    "region",
)

_BEARER_PREFIX = "bearer "


class _AwsAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Shared contract for every AWS-V3 live-event processor."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Constant-time bearer compare against `webhook_secret`.

        Defense-in-depth: the path-scoped FastAPI middleware will normally
        have rejected unauthenticated requests before the framework
        enqueues them. This check guarantees that even if the middleware
        is removed or its scoping breaks, no event reaches `handle_event`
        with an invalid bearer.
        """
        configured_secret = ocean.integration_config.get("webhook_secret")
        if not configured_secret:
            logger.error(
                "AWS live-events processor: webhook_secret is not configured; "
                "rejecting event"
            )
            return False

        provided = self._extract_bearer_token(headers)
        if not provided:
            logger.warning(
                "AWS live-events processor: missing or malformed Authorization header"
            )
            return False

        return hmac.compare_digest(provided, str(configured_secret))

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Verify the payload looks like an EventBridge envelope."""
        missing = [field for field in _REQUIRED_ENVELOPE_FIELDS if field not in payload]
        if missing:
            logger.warning(
                "AWS live-events processor: payload missing required EventBridge "
                f"fields {missing}; dropping event"
            )
            return False
        detail = payload.get("detail")
        if not isinstance(detail, dict):
            logger.warning(
                "AWS live-events processor: payload `detail` is not a JSON object; "
                "dropping event"
            )
            return False
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Route an event to this processor if it matches and the account is allowed."""
        payload = event.payload
        if not await self._matches_event(event):
            return False

        account_id = payload.get("account")
        if not account_id:
            logger.warning(
                "AWS live-events processor: payload has no `account` field; dropping"
            )
            return False

        if not await self._is_account_allowed(str(account_id)):
            logger.info(
                f"AWS live-events processor: dropping event from account {account_id} "
                f"(not in allowedAccountIds)"
            )
            return False

        return True

    @abstractmethod
    async def _matches_event(self, event: WebhookEvent) -> bool:
        """Return True if this processor handles the given EventBridge event."""

    async def _is_account_allowed(self, account_id: str) -> bool:
        """Check the account against the `allowedAccountIds` allowlist.

        When `allowedAccountIds` is unset or empty in the integration
        config, the allowlist is derived from the accounts that passed
        the auth healthcheck. This avoids the drift trap where an
        operator adds an account to the org and forgets to update the
        allowlist (and vice-versa where `["*"]` would silently
        unauthenticate every account).
        """
        configured = ocean.integration_config.get("allowed_account_ids")
        if configured:
            allowed = {str(a).strip() for a in self._coerce_to_list(configured) if a}
            return account_id in allowed

        from aws.auth.session_factory import discover_valid_account_ids

        derived = await discover_valid_account_ids()
        if not derived:
            logger.debug(
                "allowedAccountIds derivation: no validated accounts yet; "
                "allowing event through (resync healthcheck not run)"
            )
            return True
        return account_id in derived

    @staticmethod
    def _coerce_to_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value]

    @staticmethod
    def _extract_bearer_token(headers: EventHeaders) -> str | None:
        raw = headers.get("authorization") or headers.get("Authorization")
        if not raw:
            return None
        if not raw.lower().startswith(_BEARER_PREFIX):
            return None
        return raw[len(_BEARER_PREFIX) :].strip() or None

    def _reject_if_logical_region_blocked(
        self,
        resource_config: ResourceConfig,
        logical_region: str,
    ) -> WebhookEventRawResults | None:
        """Return empty results when `regionPolicy` excludes `logical_region`."""
        aws_rc = cast(AWSResourceConfig, resource_config)
        if aws_rc.selector.is_region_allowed(logical_region):
            return None
        logger.info(
            "AWS live-events processor: dropping workload region '{}' — "
            "excluded by selector.regionPolicy",
            logical_region,
        )
        return WebhookEventRawResults(
            updated_raw_results=[], deleted_raw_results=[]
        )
