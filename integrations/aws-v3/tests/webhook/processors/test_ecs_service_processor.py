"""Tests for ``EcsServiceWebhookProcessor``."""

import json
from pathlib import Path
from typing import Any

import pytest
from unittest.mock import AsyncMock

from aws.core.exporters.ecs.service.models import SingleServiceRequest
from aws.webhook.processors.ecs_service_processor import EcsServiceWebhookProcessor
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
async def test_service_action_emits_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    """An `ECS Service Action` envelope -> one call to
    `EcsServiceExporter.get_resource(...)` with the cluster and service
    parsed from `detail.clusterArn` and the top-level `resources[]` ARN."""

    payload = _load_fixture("ecs_service_action.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock(return_value={"Type": "AWS::ECS::Service"})

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(EcsServiceWebhookProcessor, "_exporter_cls", _Exporter)
    proc = EcsServiceWebhookProcessor(event)

    async def _sess(account_id: str) -> Any:
        return object()

    monkeypatch.setattr(
        "aws.webhook.processors.aws_abstract_webhook_processor.get_session_for_account",
        _sess,
    )

    res = await proc.handle_event(payload, _RC())  # type: ignore[arg-type]
    assert res.deleted_raw_results == []
    assert res.updated_raw_results == [{"Type": "AWS::ECS::Service"}]

    assert exporter_mock.call_count == 1
    (req,) = exporter_mock.call_args.args
    assert isinstance(req, SingleServiceRequest)
    assert req.cluster_name == "my-cluster"
    assert req.service_name == "my-service"


@pytest.mark.asyncio
async def test_delete_service_emits_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CT-via-EB `DeleteService` envelope -> no exporter call; emit a
    delete stub keyed on the reconstructed service ARN."""

    payload = _load_fixture("ecs_delete_service.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock()

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(EcsServiceWebhookProcessor, "_exporter_cls", _Exporter)
    proc = EcsServiceWebhookProcessor(event)

    async def _sess(account_id: str) -> Any:
        return object()

    monkeypatch.setattr(
        "aws.webhook.processors.aws_abstract_webhook_processor.get_session_for_account",
        _sess,
    )

    res = await proc.handle_event(payload, _RC())  # type: ignore[arg-type]
    exporter_mock.assert_not_called()
    assert res.updated_raw_results == []
    assert res.deleted_raw_results == [
        {
            "Type": "AWS::ECS::Service",
            "Properties": {
                "ServiceArn": "arn:aws:ecs:us-east-1:123456789012:service/my-cluster/my-service",
                "ServiceName": "my-service",
                "ClusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster",
            },
            "__ExtraContext": {"AccountId": "123456789012", "Region": "us-east-1"},
        }
    ]
