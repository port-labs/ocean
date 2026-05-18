"""Live-events `selector.regionPolicy` coverage (minimal gate in `handle_event`)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.webhook.webhook_processors.ec2_instance_webhook_processor import (
    Ec2InstanceWebhookProcessor,
)
from aws.webhook.webhook_processors.s3_bucket_webhook_processor import (
    S3BucketWebhookProcessor,
)
from integration import AWSResourceSelector, RegionPolicy
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from tests.webhook.fixtures import ec2_state_change_event, s3_create_bucket_event


def _eu_only_resource_config() -> MagicMock:
    rc = MagicMock()
    rc.selector = AWSResourceSelector(
        query=". | true",
        region_policy=RegionPolicy(allow=["eu-west-1"], deny=[]),
    )
    return rc


def _allow_us_east_resource_config() -> MagicMock:
    rc = MagicMock()
    rc.selector = AWSResourceSelector(
        query=". | true",
        region_policy=RegionPolicy(allow=["us-east-1"], deny=[]),
    )
    return rc


@pytest.mark.asyncio
async def test_ec2_blocked_when_region_policy_excludes_payload_region() -> None:
    payload = ec2_state_change_event("i-abc123", "running")
    event = WebhookEvent(trace_id="trace", payload=payload, headers={})
    processor = Ec2InstanceWebhookProcessor(event)

    mock_session_fn = AsyncMock(return_value=MagicMock(name="session"))

    with patch(
        "aws.webhook.webhook_processors.ec2_instance_webhook_processor.session_for_account",
        mock_session_fn,
    ):
        result = await processor.handle_event(payload, _eu_only_resource_config())

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    mock_session_fn.assert_not_awaited()


@pytest.mark.asyncio
async def test_ec2_continues_when_region_policy_allows_payload_region() -> None:
    payload = ec2_state_change_event("i-abc123", "running")
    event = WebhookEvent(trace_id="trace", payload=payload, headers={})
    processor = Ec2InstanceWebhookProcessor(event)

    mock_session_fn = AsyncMock(return_value=MagicMock(name="session"))
    exporter_instance = MagicMock()
    exporter_instance.get_resource = AsyncMock(
        return_value={"Type": "AWS::EC2::Instance", "Properties": {"InstanceId": "x"}}
    )

    with (
        patch(
            "aws.webhook.webhook_processors.ec2_instance_webhook_processor.session_for_account",
            mock_session_fn,
        ),
        patch(
            "aws.webhook.webhook_processors.ec2_instance_webhook_processor.EC2InstanceExporter",
            return_value=exporter_instance,
        ),
    ):
        result = await processor.handle_event(payload, _allow_us_east_resource_config())

    mock_session_fn.assert_awaited_once()
    exporter_instance.get_resource.assert_awaited_once()
    assert len(result.updated_raw_results) == 1


@pytest.mark.asyncio
async def test_s3_blocked_using_resolved_bucket_region_not_envelope_us_east_1() -> None:
    """Envelope `region` is always `us-east-1` for S3; policy must match home region."""
    payload = s3_create_bucket_event("my-bucket", location_constraint="eu-west-1")
    event = WebhookEvent(trace_id="trace", payload=payload, headers={})
    processor = S3BucketWebhookProcessor(event)

    mock_session_fn = AsyncMock(return_value=MagicMock(name="session"))

    with patch(
        "aws.webhook.webhook_processors.s3_bucket_webhook_processor.session_for_account",
        mock_session_fn,
    ):
        result = await processor.handle_event(payload, _allow_us_east_resource_config())

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    mock_session_fn.assert_not_awaited()
