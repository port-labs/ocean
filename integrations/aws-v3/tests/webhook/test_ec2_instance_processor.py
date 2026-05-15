"""Tests for `Ec2InstanceWebhookProcessor`."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.webhook.webhook_processors.ec2_instance_webhook_processor import (
    Ec2InstanceWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from tests.webhook.fixtures import ec2_state_change_event


def _processor_for(payload: dict[str, Any]) -> Ec2InstanceWebhookProcessor:
    event = WebhookEvent(trace_id="t", payload=payload, headers={})
    return Ec2InstanceWebhookProcessor(event=event)


def _resource_config(include_actions: list[str] | None = None) -> MagicMock:
    config = MagicMock()
    config.selector.include_actions = include_actions or []
    return config


class TestMatchesEvent:
    @pytest.mark.asyncio
    async def test_matches_ec2_state_change(self) -> None:
        payload = ec2_state_change_event("i-0123abc", "running")
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is True

    @pytest.mark.asyncio
    async def test_does_not_match_ecs_event(self) -> None:
        payload = ec2_state_change_event("i-0", "running")
        payload["source"] = "aws.ecs"
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is False

    @pytest.mark.asyncio
    async def test_does_not_match_other_ec2_detail_type(self) -> None:
        payload = ec2_state_change_event("i-0", "running")
        payload["detail-type"] = "EC2 Spot Instance Interruption Warning"
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is False


class TestGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_returns_ec2_instance_kind(self) -> None:
        payload = ec2_state_change_event("i-0", "running")
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor.get_matching_kinds(event) == ["AWS::EC2::Instance"]


class TestHandleEvent:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("terminal_state", ["shutting-down", "terminated"])
    async def test_terminal_state_emits_delete(self, terminal_state: str) -> None:
        payload = ec2_state_change_event("i-0123abc", terminal_state)
        processor = _processor_for(payload)

        result = await processor.handle_event(
            payload=payload, resource_config=_resource_config()
        )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        deleted = result.deleted_raw_results[0]
        assert deleted["Type"] == "AWS::EC2::Instance"
        assert deleted["Properties"]["InstanceId"] == "i-0123abc"
        assert deleted["Properties"]["InstanceArn"].endswith("instance/i-0123abc")
        assert deleted["Properties"]["State"]["Name"] == terminal_state

    @pytest.mark.asyncio
    async def test_running_state_fetches_and_upserts(self) -> None:
        payload = ec2_state_change_event("i-0123abc", "running")
        processor = _processor_for(payload)
        resource = {
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": "i-0123abc"},
        }

        fake_session = MagicMock(name="session")
        with patch(
            "aws.webhook.webhook_processors.ec2_instance_webhook_processor.session_for_account",
            new=AsyncMock(return_value=fake_session),
        ):
            with patch(
                "aws.webhook.webhook_processors.ec2_instance_webhook_processor.EC2InstanceExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(return_value=resource)

                result = await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

        assert result.updated_raw_results == [resource]
        assert result.deleted_raw_results == []
        ExporterCls.assert_called_once_with(fake_session)

    @pytest.mark.asyncio
    async def test_returns_empty_when_session_missing(self) -> None:
        payload = ec2_state_change_event("i-0123abc", "running")
        processor = _processor_for(payload)

        with patch(
            "aws.webhook.webhook_processors.ec2_instance_webhook_processor.session_for_account",
            new=AsyncMock(return_value=None),
        ):
            result = await processor.handle_event(
                payload=payload, resource_config=_resource_config()
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_resource_not_found_converts_to_delete(self) -> None:
        payload = ec2_state_change_event("i-0123abc", "running")
        processor = _processor_for(payload)

        class _NotFound(Exception):
            response = {"Error": {"Code": "ResourceNotFoundException"}}

        with patch(
            "aws.webhook.webhook_processors.ec2_instance_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.ec2_instance_webhook_processor.EC2InstanceExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(
                    side_effect=_NotFound()
                )

                result = await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1

    @pytest.mark.asyncio
    async def test_drops_event_with_missing_instance_id(self) -> None:
        payload = ec2_state_change_event("i-0", "running")
        del payload["detail"]["instance-id"]
        processor = _processor_for(payload)

        result = await processor.handle_event(
            payload=payload, resource_config=_resource_config()
        )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
