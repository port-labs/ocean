"""Tests for ``EventRouter.classify``."""

import json
from pathlib import Path
from typing import Any

from aws.core.helpers.types import ObjectKind
from aws.webhook.events import EventAction
from aws.webhook.routing.event_router import EventRouter, RoutingDecision


_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    with (_FIXTURES_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def test_classifies_ec2_running_event() -> None:
    router = EventRouter()
    payload = _load_fixture("ec2_state_change_running.json")
    decision = router.classify(payload)

    assert isinstance(decision, RoutingDecision)
    assert decision.kind == ObjectKind.EC2_INSTANCE
    assert decision.action == EventAction.UPSERT
    assert decision.identifier == "i-0abc123def4567890"


def test_classifies_ec2_terminated_event() -> None:
    router = EventRouter()
    payload = _load_fixture("ec2_state_change_terminated.json")
    decision = router.classify(payload)

    assert isinstance(decision, RoutingDecision)
    assert decision.kind == ObjectKind.EC2_INSTANCE
    assert decision.action == EventAction.DELETE
    assert decision.identifier == "i-0abc123def4567890"


def test_classifies_ecs_service_action() -> None:
    router = EventRouter()
    payload = _load_fixture("ecs_service_action.json")
    decision = router.classify(payload)

    assert isinstance(decision, RoutingDecision)
    assert decision.kind == ObjectKind.ECS_SERVICE
    assert decision.action == EventAction.UPSERT
    assert decision.identifier.startswith("arn:aws:ecs:")


def test_classifies_ecs_delete_service() -> None:
    router = EventRouter()
    payload = _load_fixture("ecs_delete_service.json")
    decision = router.classify(payload)

    assert isinstance(decision, RoutingDecision)
    assert decision.kind == ObjectKind.ECS_SERVICE
    assert decision.action == EventAction.DELETE
    assert decision.identifier == "my-cluster/my-service"


def test_classifies_lambda_update_function_event() -> None:
    router = EventRouter()
    payload = _load_fixture("lambda_update_function_code.json")
    decision = router.classify(payload)

    assert isinstance(decision, RoutingDecision)
    assert decision.kind == ObjectKind.LAMBDA_FUNCTION
    assert decision.action == EventAction.UPSERT
    assert decision.identifier == "my-function"


def test_classifies_lambda_delete_function_event() -> None:
    router = EventRouter()
    payload = _load_fixture("lambda_delete_function.json")
    decision = router.classify(payload)

    assert isinstance(decision, RoutingDecision)
    assert decision.kind == ObjectKind.LAMBDA_FUNCTION
    assert decision.action == EventAction.DELETE
    assert decision.identifier == "my-function"


def test_classifies_s3_create_bucket_event() -> None:
    router = EventRouter()
    payload = _load_fixture("s3_create_bucket.json")
    decision = router.classify(payload)

    assert isinstance(decision, RoutingDecision)
    assert decision.kind == ObjectKind.S3_BUCKET
    assert decision.action == EventAction.UPSERT
    assert decision.identifier == "my-test-bucket"


def test_classifies_s3_delete_bucket_event() -> None:
    router = EventRouter()
    payload = _load_fixture("s3_delete_bucket.json")
    decision = router.classify(payload)

    assert isinstance(decision, RoutingDecision)
    assert decision.kind == ObjectKind.S3_BUCKET
    assert decision.action == EventAction.DELETE
    assert decision.identifier == "my-test-bucket"


def test_returns_none_for_unsupported_event() -> None:
    router = EventRouter()
    decision = router.classify(
        {
            "detail-type": "Totally Unknown",
            "detail": {"foo": "bar"},
        }
    )
    assert decision is None


def test_run_instances_returns_list_of_decisions() -> None:
    router = EventRouter()
    payload = _load_fixture("ec2_run_instances.json")
    decisions = router.classify(payload)

    assert isinstance(decisions, list)
    assert [d.identifier for d in decisions] == [
        "i-00112233445566778",
        "i-00998877665544332",
    ]
    assert all(d.kind == ObjectKind.EC2_INSTANCE for d in decisions)
    assert all(d.action == EventAction.UPSERT for d in decisions)
