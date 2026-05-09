"""Tests for ``EC2InstanceWebhookProcessor``."""

import json
from pathlib import Path
from typing import Any

import pytest
from unittest.mock import AsyncMock

from aws.webhook.processors.ec2_instance_processor import EC2InstanceWebhookProcessor
from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    with (_FIXTURES_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


class _Selector:
    include_actions: list[str] = []

    def is_region_allowed(self, region: str) -> bool:
        return True


class _RC:
    selector = _Selector()


@pytest.mark.asyncio
async def test_running_state_emits_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    """`detail.state == "running"` -> `EC2InstanceExporter.get_resource(...)`
    is called, and its return shape appears in `updated_raw_results`."""

    payload = _load_fixture("ec2_state_change_running.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock(return_value={"Type": "AWS::EC2::Instance"})

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(
        "aws.webhook.processors.ec2_instance_processor.EC2InstanceExporter", _Exporter
    )
    monkeypatch.setattr(EC2InstanceWebhookProcessor, "_exporter_cls", _Exporter)
    proc = EC2InstanceWebhookProcessor(event)

    async def _sess(account_id: str) -> Any:
        return object()

    monkeypatch.setattr(
        "aws.webhook.processors.aws_abstract_webhook_processor.get_session_for_account",
        _sess,
    )

    res = await proc.handle_event(payload, _RC())  # type: ignore[arg-type]
    assert res.deleted_raw_results == []
    assert res.updated_raw_results == [{"Type": "AWS::EC2::Instance"}]

    assert exporter_mock.call_count == 1
    (req,) = exporter_mock.call_args.args
    assert isinstance(req, SingleEC2InstanceRequest)
    assert req.instance_id == "i-0abc123def4567890"


@pytest.mark.asyncio
async def test_terminated_state_emits_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """`detail.state == "terminated"` -> no exporter call; emit
    `_delete_stub(...)` in `deleted_raw_results`."""

    payload = _load_fixture("ec2_state_change_terminated.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock()

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(EC2InstanceWebhookProcessor, "_exporter_cls", _Exporter)
    proc = EC2InstanceWebhookProcessor(event)

    async def _sess(account_id: str) -> Any:
        return object()

    monkeypatch.setattr(
        "aws.webhook.processors.aws_abstract_webhook_processor.get_session_for_account",
        _sess,
    )

    res = await proc.handle_event(payload, _RC())  # type: ignore[arg-type]
    assert res.updated_raw_results == []
    assert res.deleted_raw_results == [
        {
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": "i-0abc123def4567890"},
            "__ExtraContext": {"AccountId": "123456789012", "Region": "us-east-1"},
        }
    ]
    exporter_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_instances_multiple_ids_emits_multiple_upserts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `RunInstances` envelope with N instance IDs produces N upserts in
    `updated_raw_results` (one exporter call per id)."""

    payload = _load_fixture("ec2_run_instances.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock(return_value={"Type": "AWS::EC2::Instance"})

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(EC2InstanceWebhookProcessor, "_exporter_cls", _Exporter)
    proc = EC2InstanceWebhookProcessor(event)

    async def _sess(account_id: str) -> Any:
        return object()

    monkeypatch.setattr(
        "aws.webhook.processors.aws_abstract_webhook_processor.get_session_for_account",
        _sess,
    )

    res = await proc.handle_event(payload, _RC())  # type: ignore[arg-type]
    assert res.deleted_raw_results == []
    assert exporter_mock.call_count == 2
    assert len(res.updated_raw_results) == 2
