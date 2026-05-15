"""Tests for `EcsServiceWebhookProcessor`."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.webhook.webhook_processors.ecs_service_webhook_processor import (
    EcsServiceWebhookProcessor,
    _parse_service_arn,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from tests.webhook.fixtures import (
    ecs_deployment_state_change_event,
    ecs_service_action_event,
)


def _processor_for(payload: dict[str, Any]) -> EcsServiceWebhookProcessor:
    event = WebhookEvent(trace_id="t", payload=payload, headers={})
    return EcsServiceWebhookProcessor(event=event)


def _resource_config() -> MagicMock:
    config = MagicMock()
    config.selector.include_actions = []
    return config


class TestParseServiceArn:
    def test_parses_well_formed_arn(self) -> None:
        result = _parse_service_arn(
            "arn:aws:ecs:us-east-1:123456789012:service/my-cluster/my-service"
        )
        assert result == ("my-cluster", "my-service")

    def test_returns_none_for_non_service_arn(self) -> None:
        assert (
            _parse_service_arn("arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster")
            is None
        )

    def test_returns_none_for_malformed_arn(self) -> None:
        assert _parse_service_arn("not-an-arn") is None


class TestMatchesEvent:
    @pytest.mark.asyncio
    async def test_matches_service_action(self) -> None:
        payload = ecs_service_action_event("c", "s", "SERVICE_STEADY_STATE")
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is True

    @pytest.mark.asyncio
    async def test_matches_deployment_state_change(self) -> None:
        payload = ecs_deployment_state_change_event(
            "c", "s", "SERVICE_DEPLOYMENT_IN_PROGRESS"
        )
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is True

    @pytest.mark.asyncio
    async def test_does_not_match_unrelated_ecs_detail_type(self) -> None:
        payload = ecs_service_action_event("c", "s", "SERVICE_STEADY_STATE")
        payload["detail-type"] = "ECS Task State Change"
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is False


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_service_deleted_emits_delete(self) -> None:
        payload = ecs_service_action_event("my-cluster", "my-svc", "SERVICE_DELETED")
        processor = _processor_for(payload)

        result = await processor.handle_event(
            payload=payload, resource_config=_resource_config()
        )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        deleted = result.deleted_raw_results[0]
        assert deleted["Type"] == "AWS::ECS::Service"
        assert deleted["Properties"]["ServiceName"] == "my-svc"
        assert "service/my-cluster/my-svc" in deleted["Properties"]["ServiceArn"]
        assert "cluster/my-cluster" in deleted["Properties"]["ClusterArn"]

    @pytest.mark.asyncio
    async def test_deployment_state_change_triggers_upsert(self) -> None:
        payload = ecs_deployment_state_change_event(
            "my-cluster", "my-svc", "SERVICE_DEPLOYMENT_IN_PROGRESS"
        )
        processor = _processor_for(payload)
        resource = {
            "Type": "AWS::ECS::Service",
            "Properties": {"ServiceName": "my-svc"},
        }

        with patch(
            "aws.webhook.webhook_processors.ecs_service_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.ecs_service_webhook_processor.EcsServiceExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(return_value=resource)

                result = await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

                _, kwargs = ExporterCls.return_value.get_resource.call_args
                request = (
                    ExporterCls.return_value.get_resource.call_args.args[0]
                    if ExporterCls.return_value.get_resource.call_args.args
                    else kwargs["options"]
                )

        assert result.updated_raw_results == [resource]
        assert request.service_name == "my-svc"
        assert request.cluster_name == "my-cluster"

    @pytest.mark.asyncio
    async def test_drops_event_without_service_arn(self) -> None:
        payload = ecs_deployment_state_change_event("c", "s", "FOO")
        payload["resources"] = ["arn:aws:ecs:us-east-1:123456789012:cluster/c"]
        processor = _processor_for(payload)

        result = await processor.handle_event(
            payload=payload, resource_config=_resource_config()
        )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_resource_not_found_converts_to_delete(self) -> None:
        payload = ecs_service_action_event("c", "s", "SERVICE_STEADY_STATE")
        processor = _processor_for(payload)

        class _NotFound(Exception):
            response = {"Error": {"Code": "ResourceNotFoundException"}}

        with patch(
            "aws.webhook.webhook_processors.ecs_service_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.ecs_service_webhook_processor.EcsServiceExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(
                    side_effect=_NotFound()
                )

                result = await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
