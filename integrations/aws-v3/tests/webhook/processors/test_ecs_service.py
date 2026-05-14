from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aws.core.exporters.ecs.service.models import SingleServiceRequest
from aws.webhook.processors.ecs_service import ECSServiceWebhookProcessor
from tests.webhook.conftest import make_sns_notification, make_webhook_event


def _envelope(
    event_name: str = "SERVICE_DEPLOYMENT_IN_PROGRESS",
    detail_type: str = "ECS Deployment State Change",
    cluster: str = "checkout",
    service: str = "billing",
) -> dict:
    region = "us-east-1"
    account = "111111111111"
    return {
        "version": "0",
        "id": "ev-1",
        "detail-type": detail_type,
        "source": "aws.ecs",
        "account": account,
        "time": "2026-05-14T12:00:00Z",
        "region": region,
        "resources": [
            f"arn:aws:ecs:{region}:{account}:service/{cluster}/{service}"
        ],
        "detail": {
            "eventName": event_name,
            "clusterArn": f"arn:aws:ecs:{region}:{account}:cluster/{cluster}",
        },
    }


@pytest.mark.asyncio
async def test_deployment_state_change_triggers_upsert(stub_session_resolver) -> None:
    payload = make_sns_notification(_envelope())
    event = make_webhook_event(payload)
    processor = ECSServiceWebhookProcessor(event=event)

    assert await processor.should_process_event(event) is True

    mock_exporter = AsyncMock()
    mock_exporter.get_resource = AsyncMock(
        return_value={
            "Type": "AWS::ECS::Service",
            "Properties": {"serviceName": "billing"},
        }
    )
    with patch(
        "aws.webhook.processors.ecs_service.ECSServiceWebhookProcessor.exporter_cls",
        return_value=mock_exporter,
    ):
        result = await processor.handle_event(payload, resource=None)

    assert len(result.updated_raw_results) == 1
    assert result.deleted_raw_results == []
    request = mock_exporter.get_resource.call_args.args[0]
    assert isinstance(request, SingleServiceRequest)
    assert request.service_name == "billing"
    assert request.cluster_name == "checkout"


@pytest.mark.asyncio
async def test_service_deleted_triggers_delete(stub_session_resolver) -> None:
    payload = make_sns_notification(
        _envelope(
            event_name="SERVICE_DELETED",
            detail_type="ECS Service Action",
        )
    )
    event = make_webhook_event(payload)
    processor = ECSServiceWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)

    assert result.updated_raw_results == []
    assert len(result.deleted_raw_results) == 1
    deleted = result.deleted_raw_results[0]
    assert deleted["Properties"]["ServiceName"] == "billing"
    assert deleted["Properties"]["ClusterName"] == "checkout"


@pytest.mark.asyncio
async def test_malformed_service_arn_skipped(stub_session_resolver) -> None:
    envelope = _envelope()
    envelope["resources"] = ["not-an-arn"]
    payload = make_sns_notification(envelope)
    event = make_webhook_event(payload)
    processor = ECSServiceWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
