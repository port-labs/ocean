from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.webhook.processors.lambda_function import LambdaFunctionWebhookProcessor
from tests.webhook.conftest import make_sns_notification, make_webhook_event


def _envelope(event_name: str, function_name: str = "billing-aggregator") -> dict:
    return {
        "version": "0",
        "id": "ev-1",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.lambda",
        "account": "111111111111",
        "time": "2026-05-14T12:00:00Z",
        "region": "us-east-1",
        "detail": {
            "eventSource": "lambda.amazonaws.com",
            "eventName": event_name,
            "requestParameters": {"functionName": function_name},
        },
    }


@pytest.mark.asyncio
async def test_update_function_triggers_upsert(stub_session_resolver) -> None:
    payload = make_sns_notification(
        _envelope("UpdateFunctionConfiguration20150331v2")
    )
    event = make_webhook_event(payload)
    processor = LambdaFunctionWebhookProcessor(event=event)

    assert await processor.should_process_event(event) is True

    mock_exporter = AsyncMock()
    mock_exporter.get_resource = AsyncMock(
        return_value={
            "Type": "AWS::Lambda::Function",
            "Properties": {"FunctionName": "billing-aggregator"},
        }
    )
    with patch(
        "aws.webhook.processors.lambda_function.LambdaFunctionWebhookProcessor.exporter_cls",
        return_value=mock_exporter,
    ):
        result = await processor.handle_event(payload, resource=None)

    assert len(result.updated_raw_results) == 1
    assert result.deleted_raw_results == []
    request = mock_exporter.get_resource.call_args.args[0]
    assert isinstance(request, SingleLambdaFunctionRequest)
    assert request.function_name == "billing-aggregator"


@pytest.mark.asyncio
async def test_arn_function_name_is_normalized(stub_session_resolver) -> None:
    """When CloudTrail logs an ARN as functionName, normalise to the short name."""
    arn = "arn:aws:lambda:us-east-1:111111111111:function:billing-aggregator"
    payload = make_sns_notification(_envelope("CreateFunction20150331", arn))
    event = make_webhook_event(payload)
    processor = LambdaFunctionWebhookProcessor(event=event)

    mock_exporter = AsyncMock()
    mock_exporter.get_resource = AsyncMock(return_value={"Type": "AWS::Lambda::Function"})
    with patch(
        "aws.webhook.processors.lambda_function.LambdaFunctionWebhookProcessor.exporter_cls",
        return_value=mock_exporter,
    ):
        await processor.handle_event(payload, resource=None)
    request = mock_exporter.get_resource.call_args.args[0]
    assert request.function_name == "billing-aggregator"


@pytest.mark.asyncio
async def test_delete_function_triggers_delete(stub_session_resolver) -> None:
    payload = make_sns_notification(_envelope("DeleteFunction20150331"))
    event = make_webhook_event(payload)
    processor = LambdaFunctionWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)

    assert result.updated_raw_results == []
    assert len(result.deleted_raw_results) == 1


@pytest.mark.asyncio
async def test_ignored_eventname_skipped(stub_session_resolver) -> None:
    payload = make_sns_notification(_envelope("Invoke"))
    event = make_webhook_event(payload)
    processor = LambdaFunctionWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
