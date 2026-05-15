"""Tests for `LambdaFunctionWebhookProcessor`."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.webhook.webhook_processors.lambda_function_webhook_processor import (
    LambdaFunctionWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from tests.webhook.fixtures import lambda_event


def _processor_for(payload: dict[str, Any]) -> LambdaFunctionWebhookProcessor:
    event = WebhookEvent(trace_id="t", payload=payload, headers={})
    return LambdaFunctionWebhookProcessor(event=event)


def _resource_config() -> MagicMock:
    config = MagicMock()
    config.selector.include_actions = []
    return config


class TestMatchesEvent:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "event_name",
        [
            "CreateFunction20150331",
            "UpdateFunctionConfiguration20150331v2",
            "UpdateFunctionCode20150331v2",
            "DeleteFunction20150331",
        ],
    )
    async def test_matches_versioned_event_names(self, event_name: str) -> None:
        payload = lambda_event("my-fn", event_name)
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is True

    @pytest.mark.asyncio
    async def test_does_not_match_invoke(self) -> None:
        payload = lambda_event("my-fn", "Invoke")
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is False

    @pytest.mark.asyncio
    async def test_does_not_match_when_event_source_is_different(self) -> None:
        payload = lambda_event("my-fn", "CreateFunction20150331")
        payload["detail"]["eventSource"] = "ec2.amazonaws.com"
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is False


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_delete_event_emits_delete(self) -> None:
        payload = lambda_event("my-fn", "DeleteFunction20150331")
        processor = _processor_for(payload)

        result = await processor.handle_event(
            payload=payload, resource_config=_resource_config()
        )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        deleted = result.deleted_raw_results[0]
        assert deleted["Properties"]["FunctionName"] == "my-fn"
        assert deleted["Properties"]["FunctionArn"].endswith(":function:my-fn")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "event_name",
        [
            "CreateFunction20150331",
            "UpdateFunctionConfiguration20150331v2",
            "UpdateFunctionCode20150331v2",
        ],
    )
    async def test_upsert_events_fetch_and_return(self, event_name: str) -> None:
        payload = lambda_event("my-fn", event_name)
        processor = _processor_for(payload)
        resource = {
            "Type": "AWS::Lambda::Function",
            "Properties": {"FunctionName": "my-fn"},
        }

        with patch(
            "aws.webhook.webhook_processors.lambda_function_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.lambda_function_webhook_processor.LambdaFunctionExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(return_value=resource)

                result = await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

        assert result.updated_raw_results == [resource]
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_resource_not_found_converts_to_delete(self) -> None:
        payload = lambda_event("my-fn", "UpdateFunctionConfiguration20150331v2")
        processor = _processor_for(payload)

        class _NotFound(Exception):
            response = {"Error": {"Code": "ResourceNotFoundException"}}

        with patch(
            "aws.webhook.webhook_processors.lambda_function_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.lambda_function_webhook_processor.LambdaFunctionExporter"
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
    async def test_fallback_extracts_function_name_from_arn(self) -> None:
        payload = lambda_event("ignored", "CreateFunction20150331")
        del payload["detail"]["requestParameters"]["functionName"]
        payload["detail"]["responseElements"][
            "functionArn"
        ] = "arn:aws:lambda:us-east-1:123456789012:function:fallback-fn"
        processor = _processor_for(payload)

        with patch(
            "aws.webhook.webhook_processors.lambda_function_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.lambda_function_webhook_processor.LambdaFunctionExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(return_value={"x": 1})

                await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

                request = ExporterCls.return_value.get_resource.call_args.args[0]

        assert request.function_name == "fallback-fn"
