"""Tests for ``AwsAbstractWebhookProcessor`` (auth, validation, gates, ``handle_event``)."""

from __future__ import annotations

from typing import Any

import pytest

from aws.core.helpers.types import ObjectKind
from aws.webhook.events import EventAction
from aws.webhook.routing.event_router import EventRouter, RoutingDecision
from aws.webhook.processors.aws_abstract_webhook_processor import (
    AwsAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)


class _FakeRequest:
    def __init__(self, body: bytes) -> None:
        self._body = body

    async def body(self) -> bytes:
        return self._body


class _TestExporter:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_resource(self, options: Any) -> dict[str, Any]:
        return {"id": "ok", "options": getattr(options, "identifier", None)}

    async def get_paginated_resources(self, options: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


class _TestProcessor(AwsAbstractWebhookProcessor):
    _kind = ObjectKind.EC2_INSTANCE
    _exporter_cls = _TestExporter  # type: ignore[assignment]

    def _build_single_request(
        self,
        identifier: str,
        region: str,
        account_id: str,
        include: list[str],
    ) -> Any:
        class Req:
            def __init__(self, identifier: str) -> None:
                self.identifier = identifier

        return Req(identifier)

    def _delete_stub(
        self, identifier: str, account_id: str, region: str
    ) -> dict[str, Any]:
        return {"identifier": identifier, "account_id": account_id, "region": region}


def test_authenticate_rejects_bad_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    """A header that does not match the HMAC of the raw body returns False;
    Ocean's manager turns that into HTTP 401 upstream."""

    async def _run() -> None:
        event = WebhookEvent(
            trace_id="t",
            payload={},
            headers={"x-port-signature": "sha256=bad"},
            original_request=_FakeRequest(b"body"),  # type: ignore[arg-type]
        )
        proc = _TestProcessor(event)

        from aws.webhook.processors import aws_abstract_webhook_processor as mod

        monkeypatch.setattr(
            mod,
            "ocean",
            type("_O", (), {"integration_config": {"webhook_secret": "s"}})(),
        )

        def fake_verify(secret: str, body: bytes, header_value: str | None) -> bool:
            return False

        monkeypatch.setattr(mod, "verify_signature", fake_verify)
        assert await proc.authenticate(event.payload, event.headers) is False

    import asyncio

    asyncio.run(_run())


def test_authenticate_accepts_valid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    """A header matching `compute_signature(secret, body)` returns True."""

    async def _run() -> None:
        event = WebhookEvent(
            trace_id="t",
            payload={},
            headers={"x-port-signature": "sha256=ok"},
            original_request=_FakeRequest(b"body"),  # type: ignore[arg-type]
        )
        proc = _TestProcessor(event)

        from aws.webhook.processors import aws_abstract_webhook_processor as mod

        monkeypatch.setattr(
            mod,
            "ocean",
            type("_O", (), {"integration_config": {"webhook_secret": "s"}})(),
        )

        def fake_verify(secret: str, body: bytes, header_value: str | None) -> bool:
            return True

        monkeypatch.setattr(mod, "verify_signature", fake_verify)
        assert await proc.authenticate(event.payload, event.headers) is True

    import asyncio

    asyncio.run(_run())


def test_validate_payload_eb_envelope() -> None:
    """`validate_payload` rejects payloads missing any of `id`, `source`,
    `detail-type`, `account`, `region`, `detail`."""

    async def _run() -> None:
        event = WebhookEvent(trace_id="t", payload={}, headers={})
        proc = _TestProcessor(event)

        assert (
            await proc.validate_payload(
                {
                    "id": "1",
                    "source": "aws.ec2",
                    "detail-type": "x",
                    "account": "123",
                    "region": "us-east-1",
                    "detail": {},
                }
            )
            is True
        )
        assert await proc.validate_payload({"id": "1"}) is False

    import asyncio

    asyncio.run(_run())


def test_should_process_event_matches_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    """`should_process_event` returns True only when the router classifies
    the envelope into the processor's `_kind`."""

    decisions = iter(
        [
            RoutingDecision(
                kind=ObjectKind.EC2_INSTANCE, action=EventAction.UPSERT, identifier="i"
            ),
            RoutingDecision(
                kind=ObjectKind.S3_BUCKET, action=EventAction.UPSERT, identifier="b"
            ),
        ]
    )

    def fake_classify(self: Any, payload: dict[str, Any]) -> RoutingDecision:
        return next(decisions)

    monkeypatch.setattr(EventRouter, "classify", fake_classify)

    async def _run() -> None:
        event = WebhookEvent(trace_id="t", payload={"detail": {}}, headers={})
        proc = _TestProcessor(event)

        assert await proc.should_process_event(event) is True
        assert await proc.should_process_event(event) is False

    import asyncio

    asyncio.run(_run())


def test_handle_event_skips_when_region_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """If `AWSResourceSelector.is_region_allowed(region)` is False, return
    empty `WebhookEventRawResults` and log `outcome=skipped:region_denied`."""

    def fake_classify(self: Any, payload: dict[str, Any]) -> RoutingDecision:
        return RoutingDecision(
            kind=ObjectKind.EC2_INSTANCE, action=EventAction.UPSERT, identifier="i"
        )

    monkeypatch.setattr(EventRouter, "classify", fake_classify)

    async def _run() -> None:
        payload = {
            "id": "1",
            "account": "123",
            "region": "us-east-1",
            "detail-type": "x",
            "source": "aws.ec2",
            "detail": {},
        }
        event = WebhookEvent(trace_id="t", payload=payload, headers={})
        proc = _TestProcessor(event)

        class Selector:
            def is_region_allowed(self, region: str) -> bool:
                return False

        class RC:
            selector = Selector()

        res = await proc.handle_event(payload, RC())  # type: ignore[arg-type]
        assert isinstance(res, WebhookEventRawResults)
        assert res.updated_raw_results == []
        assert res.deleted_raw_results == []

    import asyncio

    asyncio.run(_run())


def test_handle_event_skips_when_account_not_onboarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `get_session_for_account(account_id)` returns None, emit empty
    results and log `outcome=skipped:account_not_onboarded`."""

    def fake_classify(self: Any, payload: dict[str, Any]) -> RoutingDecision:
        return RoutingDecision(
            kind=ObjectKind.EC2_INSTANCE, action=EventAction.UPSERT, identifier="i"
        )

    monkeypatch.setattr(EventRouter, "classify", fake_classify)

    async def _run() -> None:
        payload = {
            "id": "1",
            "account": "123",
            "region": "us-east-1",
            "detail-type": "x",
            "source": "aws.ec2",
            "detail": {},
        }
        event = WebhookEvent(trace_id="t", payload=payload, headers={})
        proc = _TestProcessor(event)

        from aws.webhook.processors import aws_abstract_webhook_processor as mod

        async def fake_get_session_for_account(account_id: str) -> Any:
            return None

        monkeypatch.setattr(
            mod, "get_session_for_account", fake_get_session_for_account
        )

        class Selector:
            def is_region_allowed(self, region: str) -> bool:
                return True

        class RC:
            selector = Selector()

        res = await proc.handle_event(payload, RC())  # type: ignore[arg-type]
        assert res.updated_raw_results == []
        assert res.deleted_raw_results == []

    import asyncio

    asyncio.run(_run())


def test_duplicate_event_id_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replay of the same EventBridge ``id`` for the **same** resource mapping
    short-circuits; the second call hits ``_successful_handle_keys``."""

    def fake_classify(self: Any, payload: dict[str, Any]) -> RoutingDecision:
        return RoutingDecision(
            kind=ObjectKind.EC2_INSTANCE, action=EventAction.DELETE, identifier="i"
        )

    monkeypatch.setattr(EventRouter, "classify", fake_classify)

    async def _run() -> None:
        payload = {
            "id": "dup",
            "account": "123",
            "region": "us-east-1",
            "detail-type": "x",
            "source": "aws.ec2",
            "detail": {},
        }
        event = WebhookEvent(trace_id="t", payload=payload, headers={})
        proc = _TestProcessor(event)

        from aws.webhook.processors import aws_abstract_webhook_processor as mod

        async def fake_get_session_for_account(account_id: str) -> Any:
            return object()

        monkeypatch.setattr(
            mod, "get_session_for_account", fake_get_session_for_account
        )

        class Selector:
            def is_region_allowed(self, region: str) -> bool:
                return True

        class RC:
            selector = Selector()

        first = await proc.handle_event(payload, RC())  # type: ignore[arg-type]
        second = await proc.handle_event(payload, RC())  # type: ignore[arg-type]
        assert first.deleted_raw_results
        assert second.updated_raw_results == []
        assert second.deleted_raw_results == []

    import asyncio

    asyncio.run(_run())


def test_duplicate_event_two_distinct_resource_configs_both_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same ``event[\"id\"]`` with different fingerprints must both run (Port may
    call ``handle_event`` once per mapping). Cached refetches share one AWS ``get_resource``.
    """

    def fake_classify(self: Any, payload: dict[str, Any]) -> RoutingDecision:
        return RoutingDecision(
            kind=ObjectKind.EC2_INSTANCE, action=EventAction.UPSERT, identifier="i"
        )

    monkeypatch.setattr(EventRouter, "classify", fake_classify)

    exporter_calls = 0

    class _CountingExporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        async def get_resource(self, options: Any) -> dict[str, Any]:
            nonlocal exporter_calls
            exporter_calls += 1
            return {
                "call": exporter_calls,
                "identifier": getattr(options, "identifier", ""),
            }

        async def get_paginated_resources(self, options: Any) -> Any:
            raise NotImplementedError

    async def _run() -> None:
        payload = {
            "id": "evt-shared",
            "account": "123",
            "region": "us-east-1",
            "detail-type": "x",
            "source": "aws.ec2",
            "detail": {},
        }
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        monkeypatch.setattr(_TestProcessor, "_exporter_cls", _CountingExporter)

        from aws.webhook.processors import aws_abstract_webhook_processor as mod

        async def fake_get_session_for_account(account_id: str) -> Any:
            return object()

        monkeypatch.setattr(
            mod, "get_session_for_account", fake_get_session_for_account
        )

        class Selector:
            include_actions: list[str] = []
            query: str = "q"

            def is_region_allowed(self, region: str) -> bool:
                return True

        class RC1:
            kind = "mapping-a"
            selector = Selector()

        class RC2:
            kind = "mapping-b"
            selector = Selector()

        proc = _TestProcessor(event)
        r1 = await proc.handle_event(payload, RC1())  # type: ignore[arg-type]
        r2 = await proc.handle_event(payload, RC2())  # type: ignore[arg-type]

        assert r1.updated_raw_results and r1.updated_raw_results[0]["call"] == 1
        assert r2.updated_raw_results and r2.updated_raw_results[0]["call"] == 1
        assert exporter_calls == 1

    import asyncio

    asyncio.run(_run())


def test_transient_exporter_error_retries_do_not_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``get_resource`` may raise once; retries must not hit the success idempotency
    cache until a full completion."""

    exporter_calls = 0

    class _FlakyExporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        async def get_resource(self, options: Any) -> dict[str, Any]:
            nonlocal exporter_calls
            exporter_calls += 1
            if exporter_calls == 1:
                raise TimeoutError("transient downstream")
            return {"recovered": True}

        async def get_paginated_resources(self, options: Any) -> Any:
            raise NotImplementedError

    def fake_classify(self: Any, payload: dict[str, Any]) -> RoutingDecision:
        return RoutingDecision(
            kind=ObjectKind.EC2_INSTANCE, action=EventAction.UPSERT, identifier="i"
        )

    monkeypatch.setattr(EventRouter, "classify", fake_classify)

    async def _run() -> None:
        payload = {
            "id": "retry-evt",
            "account": "123",
            "region": "us-east-1",
            "detail-type": "x",
            "source": "aws.ec2",
            "detail": {},
        }
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        monkeypatch.setattr(_TestProcessor, "_exporter_cls", _FlakyExporter)

        from aws.webhook.processors import aws_abstract_webhook_processor as mod

        async def fake_get_session_for_account(account_id: str) -> Any:
            return object()

        monkeypatch.setattr(
            mod, "get_session_for_account", fake_get_session_for_account
        )

        class Selector:
            include_actions: list[str] = []

            def is_region_allowed(self, region: str) -> bool:
                return True

        class RC:
            selector = Selector()

        proc = _TestProcessor(event)
        rc = RC()

        caught: list[Any] = []
        try:
            await proc.handle_event(payload, rc)  # type: ignore[arg-type]
        except TimeoutError:
            caught.append(True)

        assert caught == [True]
        res = await proc.handle_event(payload, rc)  # type: ignore[arg-type]
        assert res.updated_raw_results == [{"recovered": True}]
        assert exporter_calls == 2

    import asyncio

    asyncio.run(_run())


def test_resource_not_found_on_upsert_becomes_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `get_resource(...)` raises `ResourceNotFoundException` on an
    UPSERT, the processor converts the result into a DELETE."""

    def fake_classify(self: Any, payload: dict[str, Any]) -> RoutingDecision:
        return RoutingDecision(
            kind=ObjectKind.EC2_INSTANCE, action=EventAction.UPSERT, identifier="i"
        )

    monkeypatch.setattr(EventRouter, "classify", fake_classify)

    async def _run() -> None:
        payload = {
            "id": "1",
            "account": "123",
            "region": "us-east-1",
            "detail-type": "x",
            "source": "aws.ec2",
            "detail": {},
        }
        event = WebhookEvent(trace_id="t", payload=payload, headers={})
        proc = _TestProcessor(event)

        from aws.webhook.processors import aws_abstract_webhook_processor as mod

        async def fake_get_session_for_account(account_id: str) -> Any:
            return object()

        monkeypatch.setattr(
            mod, "get_session_for_account", fake_get_session_for_account
        )

        class NotFound(Exception):
            def __init__(self) -> None:
                self.response = {"Error": {"Code": "ResourceNotFoundException"}}

        async def raise_not_found(self: Any, options: Any) -> dict[str, Any]:
            raise NotFound()

        monkeypatch.setattr(_TestExporter, "get_resource", raise_not_found)

        class Selector:
            def is_region_allowed(self, region: str) -> bool:
                return True

        class RC:
            selector = Selector()

        res = await proc.handle_event(payload, RC())  # type: ignore[arg-type]
        assert res.updated_raw_results == []
        assert (
            res.deleted_raw_results and res.deleted_raw_results[0]["identifier"] == "i"
        )

    import asyncio

    asyncio.run(_run())
