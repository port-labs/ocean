from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from aws.webhook.processors.ec2_instance import EC2InstanceWebhookProcessor
from tests.webhook.conftest import make_sns_notification, make_webhook_event


def _envelope(state: str, instance_id: str = "i-0123456789abcdef0") -> dict:
    return {
        "version": "0",
        "id": "ev-1",
        "detail-type": "EC2 Instance State-change Notification",
        "source": "aws.ec2",
        "account": "111111111111",
        "time": "2026-05-14T12:00:00Z",
        "region": "us-east-1",
        "resources": [
            f"arn:aws:ec2:us-east-1:111111111111:instance/{instance_id}"
        ],
        "detail": {"instance-id": instance_id, "state": state},
    }


@pytest.mark.asyncio
async def test_running_state_triggers_upsert(stub_session_resolver) -> None:
    payload = make_sns_notification(_envelope("running"))
    event = make_webhook_event(payload)
    processor = EC2InstanceWebhookProcessor(event=event)

    assert await processor.should_process_event(event) is True

    mock_exporter = AsyncMock()
    mock_exporter.get_resource = AsyncMock(
        return_value={
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": "i-0123456789abcdef0"},
        }
    )
    with patch(
        "aws.webhook.processors.ec2_instance.EC2InstanceWebhookProcessor.exporter_cls",
        return_value=mock_exporter,
    ) as exporter_cls:
        result = await processor.handle_event(payload, resource=None)

    assert len(result.updated_raw_results) == 1
    assert result.deleted_raw_results == []
    exporter_cls.assert_called_once()
    request = mock_exporter.get_resource.call_args.args[0]
    assert isinstance(request, SingleEC2InstanceRequest)
    assert request.instance_id == "i-0123456789abcdef0"
    assert request.account_id == "111111111111"
    assert request.region == "us-east-1"


@pytest.mark.asyncio
async def test_terminated_state_triggers_delete(stub_session_resolver) -> None:
    payload = make_sns_notification(
        _envelope("terminated"), message_id="terminate-1"
    )
    event = make_webhook_event(payload)
    processor = EC2InstanceWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)

    assert result.updated_raw_results == []
    assert len(result.deleted_raw_results) == 1
    deleted = result.deleted_raw_results[0]
    assert deleted["Type"] == "AWS::EC2::Instance"
    assert deleted["Properties"]["InstanceId"] == "i-0123456789abcdef0"
    # No exporter call should happen on delete.
    stub_session_resolver.get.assert_not_called()


@pytest.mark.asyncio
async def test_shutting_down_state_triggers_delete(stub_session_resolver) -> None:
    payload = make_sns_notification(_envelope("shutting-down"))
    event = make_webhook_event(payload)
    processor = EC2InstanceWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)

    assert result.updated_raw_results == []
    assert len(result.deleted_raw_results) == 1


@pytest.mark.asyncio
async def test_missing_instance_id_skipped(stub_session_resolver) -> None:
    envelope = _envelope("running")
    envelope["detail"].pop("instance-id")
    payload = make_sns_notification(envelope)
    event = make_webhook_event(payload)
    processor = EC2InstanceWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
