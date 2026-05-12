"""Abstract base class for all AWS-V3 live-event processors.

Every concrete per-kind processor (EC2, ECS service, Lambda, S3) inherits from
this class. It mirrors `_GithubAbstractWebhookProcessor` from the GitHub
integration in spirit: a single class concentrates the cross-cutting concerns
(authentication, validation, idempotency, dispatch) so subclasses only need to
encode the per-kind extraction logic.

Lifecycle (driven by Ocean's `LiveEventsProcessorManager`):

    authenticate(payload, headers)  -> verify HMAC
    validate_payload(payload)       -> sanity-check the EventBridge envelope
    should_process_event(event)     -> match this processor's `_kind`
    get_matching_kinds(event)       -> [self._kind]
    handle_event(payload, resource) -> orchestrate refetch + emit results

Session lookup is implemented in ``aws.auth.session_factory.get_session_for_account``.
High level:

1. Calls ``await AccountStrategyFactory.create()`` — idempotent because the
   factory caches `_cached_strategy`. No re-authentication on the hot path.
2. Reads the strategy's ``valid_sessions: dict[str, AioSession]``
   (already exposed as a property on the Organizations and MultiAccount
   strategies; the SingleAccount strategy will surface its single session
   under the same name).
3. Reverses the role-ARN -> session map by parsing each ARN with
   `aws.auth.utils.extract_account_from_arn`. The reverse map is computed
   lazily once per strategy instance and cached on it, so per-event lookup
   is O(1) after the first call.
4. Returns the matching `AioSession`, or `None` (logged as a structured
   warning carrying ``account_id``) if the account is not onboarded.

Concurrency safety:

* Webhook workers are read-only consumers of the strategy cache. They run on
  the same asyncio event loop, so dict reads are safe without explicit locks.
* The first call may trigger ``healthcheck()`` if no resync has run yet;
  ``AccountStrategyFactory.create()`` is itself idempotent, so concurrent
  callers all converge on the same instance.
* **Constraint**: webhook code must never call
  ``clear_aws_account_sessions()`` — that belongs exclusively to the resync
  lifecycle hooks in ``main.py``.

Details live next to the consumer here; see ``get_session_for_account`` for
the exact implementation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any, ClassVar, Type

from aws.core.helpers.types import ObjectKind
from aws.core.helpers.utils import is_resource_not_found_exception
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.auth.session_factory import get_session_for_account
from aws.webhook.routing.event_router import EventRouter
from aws.webhook.routing.event_router import RoutingDecision
from aws.webhook.security.signature import SIGNATURE_HEADER, verify_signature
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
from port_ocean.context.ocean import ocean


_PROCESS_CACHE_MAXSIZE: int = 10_000
_PROCESS_CACHE_TTL_SECONDS: int = 600  # 10 minutes


def _coerce_plain_selector(selector: Any) -> dict[str, Any]:
    if selector is None:
        return {}

    md = getattr(selector, "model_dump", None)
    if callable(md):
        try:
            return md(mode="json", by_alias=True)
        except TypeError:
            return md(by_alias=True)
    dg = getattr(selector, "dict", None)
    if callable(dg):
        return dg(by_alias=True)

    region_policy = getattr(selector, "region_policy", None)
    if region_policy is None:
        rp: dict[str, Any] | str = ""
    else:
        rp_md = getattr(region_policy, "model_dump", None)
        if callable(rp_md):
            try:
                rp = rp_md(mode="json", by_alias=True)
            except TypeError:
                rp = rp_md(by_alias=True)
        elif callable(getattr(region_policy, "dict", None)):
            rp = getattr(region_policy, "dict")(by_alias=True)
        else:
            rp = {
                "allow": list(getattr(region_policy, "allow", []) or []),
                "deny": list(getattr(region_policy, "deny", []) or []),
            }

    return {
        "query": getattr(selector, "query", ""),
        "region_policy": rp,
        "include_actions": list(getattr(selector, "include_actions", []) or []),
    }


def _coerce_plain_port(port_section: Any) -> dict[str, Any]:
    if port_section is None:
        return {}
    md = getattr(port_section, "model_dump", None)
    if callable(md):
        try:
            return md(mode="json", by_alias=True)
        except TypeError:
            return md(by_alias=True)
    dg = getattr(port_section, "dict", None)
    if callable(dg):
        return dg(by_alias=True)
    return {}


def _resource_config_identity_payload(
    resource_config: ResourceConfig | Any,
) -> dict[str, Any]:
    """Snapshot of mapping-relevant ``ResourceConfig`` fields for fingerprints."""

    dump = getattr(resource_config, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json", by_alias=True)
        except TypeError:
            pass
        return dump(by_alias=True)
    dg = getattr(resource_config, "dict", None)
    if callable(dg):
        return dg(by_alias=True)
    return {
        "kind": getattr(resource_config, "kind", ""),
        "selector": _coerce_plain_selector(getattr(resource_config, "selector", None)),
        "port": _coerce_plain_port(getattr(resource_config, "port", None)),
    }


def _resource_config_fingerprint_hash(resource_config: ResourceConfig | Any) -> str:
    """Stable fingerprint so distinct Port mappings aren't suppressed per event id."""

    data = _resource_config_identity_payload(resource_config)
    canonical = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(canonical).hexdigest()


class AwsAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Shared lifecycle for AWS live event processors.

    Subclasses must declare:

    * :attr:`_kind` — the `ObjectKind` this processor handles.
    * :attr:`_exporter_cls` — the `IResourceExporter` subclass used to refetch
      authoritative state.

    Subclasses must implement:

    * :meth:`_extract_identifier` — extract the resource identifier from the
      EventBridge envelope (a single string for most kinds).
    * :meth:`_build_single_request` — build the per-kind ``Single*Request``
      Pydantic model the exporter expects.
    * :meth:`_delete_stub` — produce the minimal CFN-shaped envelope used
      when emitting a deletion (no AWS API call is made for deletes).
    """

    _kind: ClassVar[ObjectKind]
    _exporter_cls: ClassVar[Type[IResourceExporter]]

    # (event_id + resource fingerprint) -> completion time (epoch seconds).
    # Only populated after ``handle_event`` finishes without raising, so retries
    # after transient ``get_resource`` failures are not misclassified as dupes.
    _successful_handle_keys: ClassVar[dict[str, float]] = {}
    """Per-(webhook,mapping) idempotency, shared across all subclasses.

    A hit short-circuits to empty ``WebhookEventRawResults``
    (``outcome=skipped:duplicate``). Cross-process de-duplication is not
    attempted; Port-side upsert remains the ultimate backstop.
    """

    # Dedupes exporter work when Ocean invokes ``handle_event`` once per matching
    # ``ResourceConfig`` with identical refetch semantics (same kind + includes).
    _refetched_raw_cache: ClassVar[
        dict[str, tuple[float, list[dict[str, Any]], list[dict[str, Any]]]]
    ] = {}

    _router: ClassVar[EventRouter] = EventRouter()
    """Stateless classifier shared across instances."""

    @classmethod
    def _prune_process_caches(cls, now: float) -> None:
        cutoff = now - _PROCESS_CACHE_TTL_SECONDS

        def _expire_dict(ts_map: dict[str, float]) -> None:
            if not ts_map:
                return
            for key, ts in list(ts_map.items()):
                if ts < cutoff:
                    ts_map.pop(key, None)

        _expire_dict(cls._successful_handle_keys)

        if cls._refetched_raw_cache:
            for key, tup in list(cls._refetched_raw_cache.items()):
                inserted, _, _ = tup
                if inserted < cutoff:
                    cls._refetched_raw_cache.pop(key, None)

        # Bounded size (best-effort, not strict LRU).
        while len(cls._successful_handle_keys) > _PROCESS_CACHE_MAXSIZE:
            oldest = min(cls._successful_handle_keys.items(), key=lambda kv: kv[1])[0]
            cls._successful_handle_keys.pop(oldest, None)
        while len(cls._refetched_raw_cache) > _PROCESS_CACHE_MAXSIZE:
            oldest = min(cls._refetched_raw_cache.items(), key=lambda kv: kv[1][0])[0]
            cls._refetched_raw_cache.pop(oldest, None)

    @classmethod
    def _successful_handle_cache_key(cls, event_id: str, resource_fp: str) -> str:
        return f"{event_id}\x1f{resource_fp}"

    def _refetch_cache_key(self, event_id: str, include: list[str]) -> str:
        payload = {
            "event_id": event_id,
            "kind": self._kind,
            "include": sorted(include),
        }
        canonical = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def _consume_successful_duplicate(cls, composite_key: str) -> bool:
        """Return True if this composite key was already fully processed."""

        cls._prune_process_caches(time.time())
        return composite_key in cls._successful_handle_keys

    @classmethod
    def _remember_successful_handle(cls, composite_key: str, now: float) -> None:
        cls._successful_handle_keys[composite_key] = now

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Verify the inbound HMAC signature on the original request body.

        Returns ``False`` for missing, malformed, or mismatched signatures;
        Ocean turns that into HTTP 401 upstream.
        """

        # Spec may use ``webhookSecret``; Ocean often normalizes to ``webhook_secret``.
        secret = ocean.integration_config.get(
            "webhook_secret"
        ) or ocean.integration_config.get("webhookSecret")
        if not isinstance(secret, str) or not secret:
            return False

        request = self.event._original_request
        if request is None:
            return False

        header_value = headers.get(SIGNATURE_HEADER)
        if header_value is None:
            # Header keys may be mixed case; try lowercase map.
            lowered = {k.lower(): v for k, v in headers.items() if isinstance(k, str)}
            header_value = lowered.get(SIGNATURE_HEADER)
        if header_value is None:
            return False

        body = await request.body()
        if not isinstance(body, (bytes, bytearray)):
            return False
        return verify_signature(secret, bytes(body), header_value)

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the structural shape of the EventBridge envelope.

        Required top-level keys: ``id``, ``source``, ``detail-type``,
        ``account``, ``region``, ``detail``. Anything else is a misconfigured
        forwarder and must be rejected.
        """

        required_str_keys = ["id", "source", "detail-type", "account", "region"]
        for key in required_str_keys:
            value = payload.get(key)
            if not isinstance(value, str) or not value:
                return False
        return isinstance(payload.get("detail"), dict)

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """True when :attr:`_router` classifies the payload as this processor's
        :attr:`_kind`. For a list of decisions (e.g. ``RunInstances``), every
        item must match :attr:`_kind`.
        """

        decision = self._router.classify(event.payload)
        if decision is None:
            return False
        if isinstance(decision, list):
            return bool(decision) and all(d.kind == self._kind for d in decision)
        return decision.kind == self._kind

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the single `ObjectKind` this processor handles."""

        return [self._kind]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Idempotency, region and account gates, classify, then upsert via
        exporter or emit a delete stub; ``ResourceNotFound`` on upsert becomes
        delete.
        """

        event_id = payload.get("id")
        if not isinstance(event_id, str) or not event_id:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        resource_fp = _resource_config_fingerprint_hash(resource_config)
        handle_key = self._successful_handle_cache_key(event_id, resource_fp)

        if self._consume_successful_duplicate(handle_key):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        decision = self._router.classify(payload)
        if decision is None:
            self._remember_successful_handle(handle_key, time.time())
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        account_id = payload.get("account")
        region = payload.get("region")
        if not isinstance(account_id, str) or not isinstance(region, str):
            self._remember_successful_handle(handle_key, time.time())
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        selector = getattr(resource_config, "selector", None)
        is_region_allowed = getattr(selector, "is_region_allowed", None)
        if callable(is_region_allowed) and not is_region_allowed(region):
            self._remember_successful_handle(handle_key, time.time())
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        session = await get_session_for_account(account_id)
        if session is None:
            self._remember_successful_handle(handle_key, time.time())
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        include: list[str] = []
        if hasattr(resource_config, "selector") and getattr(
            resource_config.selector, "include_actions", None
        ):
            include = list(getattr(resource_config.selector, "include_actions"))

        refetch_key = self._refetch_cache_key(event_id, include)
        now_before_fetch = time.time()
        cls = type(self)
        cls._prune_process_caches(now_before_fetch)

        cached = cls._refetched_raw_cache.get(refetch_key)
        if cached is not None:
            inserted, cached_updated, cached_deleted = cached
            updated = copy.deepcopy(cached_updated)
            deleted = copy.deepcopy(cached_deleted)
        else:
            decisions_list: list[RoutingDecision] = (
                decision if isinstance(decision, list) else [decision]
            )

            updated = []
            deleted = []

            for d in decisions_list:
                if d.action.value == "delete":
                    deleted.append(self._delete_stub(d.identifier, account_id, region))
                    continue

                exporter = self._exporter_cls(session)
                request_model = self._build_single_request(
                    identifier=d.identifier,
                    region=region,
                    account_id=account_id,
                    include=include,
                )
                try:
                    updated.append(await exporter.get_resource(request_model))
                except Exception as e:
                    if is_resource_not_found_exception(e):
                        deleted.append(
                            self._delete_stub(d.identifier, account_id, region)
                        )
                        continue
                    raise

            now_cached = time.time()
            cls._refetched_raw_cache[refetch_key] = (
                now_cached,
                copy.deepcopy(updated),
                copy.deepcopy(deleted),
            )
            cls._prune_process_caches(now_cached)

        results = WebhookEventRawResults(
            updated_raw_results=updated,
            deleted_raw_results=deleted,
            webhook_trace_id=self.event.trace_id,
            created_at=self.event.created_at,
        )
        results.original_webhook = payload
        results.original_headers = self.event.headers
        self._remember_successful_handle(handle_key, time.time())
        return results

    # ----- Subclass extension points -----------------------------------

    def _extract_identifier(self, payload: EventPayload) -> str:
        """Return the resource identifier carried by this event.

        For most kinds this is a single string (e.g. instance id, function
        name, bucket name, service name). For multi-id CloudTrail events
        such as ``RunInstances``, the *router* expands one envelope into
        multiple `RoutingDecision`s, each carrying its own identifier — so
        subclasses still implement a single-string contract here.
        """

        raise NotImplementedError

    def _build_single_request(
        self,
        identifier: str,
        region: str,
        account_id: str,
        include: list[str],
    ) -> ResourceRequestModel:
        """Build the per-kind ``Single*Request`` for the exporter."""

        raise NotImplementedError

    def _delete_stub(
        self, identifier: str, account_id: str, region: str
    ) -> dict[str, Any]:
        """Build the minimal CFN-shaped envelope for a deletion.

        Must contain enough of `Properties` for the JQ ``identifier``
        mapping in `.port/resources/port-app-config.yml` to resolve. No AWS
        API call is made for deletes.
        """

        raise NotImplementedError
