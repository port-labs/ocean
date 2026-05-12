"""Tests for LambdaLiveEventProcessor — upsert and delete correctness."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession

from aws.live_events.processors.aws_lambda import LambdaLiveEventProcessor
from tests.live_events.conftest import make_eventbridge_event

_ACCOUNT = "123456789012"
_REGION = "eu-west-1"
_DETAIL_TYPE = "AWS API Call via CloudTrail"


def _lambda_event(event_name: str, function_name: str) -> dict:
    return make_eventbridge_event(
        _DETAIL_TYPE,
        {
            "eventSource": "lambda.amazonaws.com",
            "eventName": event_name,
            "requestParameters": {"functionName": function_name},
        },
        account=_ACCOUNT,
        region=_REGION,
        source="aws.cloudtrail",
    )


@pytest.fixture
def processor() -> LambdaLiveEventProcessor:
    return LambdaLiveEventProcessor()


@pytest.fixture
def mock_session() -> AioSession:
    return MagicMock(spec=AioSession)


class TestLambdaLiveEventProcessor:
    # -----------------------------------------------------------------------
    # can_handle
    # -----------------------------------------------------------------------

    def test_can_handle_create_function(self, processor: LambdaLiveEventProcessor) -> None:
        detail = {"eventSource": "lambda.amazonaws.com", "eventName": "CreateFunction20150331"}
        assert processor.can_handle(_DETAIL_TYPE, detail) is True

    def test_can_handle_update_function_code(self, processor: LambdaLiveEventProcessor) -> None:
        detail = {
            "eventSource": "lambda.amazonaws.com",
            "eventName": "UpdateFunctionCode20150331v2",
        }
        assert processor.can_handle(_DETAIL_TYPE, detail) is True

    def test_can_handle_delete_function(self, processor: LambdaLiveEventProcessor) -> None:
        detail = {"eventSource": "lambda.amazonaws.com", "eventName": "DeleteFunction20150331"}
        assert processor.can_handle(_DETAIL_TYPE, detail) is True

    def test_cannot_handle_non_lambda_event(self, processor: LambdaLiveEventProcessor) -> None:
        detail = {"eventSource": "ec2.amazonaws.com", "eventName": "RunInstances"}
        assert processor.can_handle(_DETAIL_TYPE, detail) is False

    def test_cannot_handle_untracked_lambda_event(self, processor: LambdaLiveEventProcessor) -> None:
        detail = {"eventSource": "lambda.amazonaws.com", "eventName": "GetFunction"}
        assert processor.can_handle(_DETAIL_TYPE, detail) is False

    # -----------------------------------------------------------------------
    # Lambda updated → upsert correctness
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_lambda_updated_upserts_resource(
        self, processor: LambdaLiveEventProcessor, mock_session: AioSession
    ) -> None:
        fake_resource = {
            "Type": "AWS::Lambda::Function",
            "Properties": {
                "FunctionName": "my-func",
                "FunctionArn": f"arn:aws:lambda:{_REGION}:{_ACCOUNT}:function:my-func",
                "Runtime": "python3.12",
            },
        }

        with patch(
            "aws.live_events.processors.aws_lambda.LambdaFunctionExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)

            event = _lambda_event("UpdateFunctionCode20150331v2", "my-func")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == [fake_resource]
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_lambda_created_upserts_resource(
        self, processor: LambdaLiveEventProcessor, mock_session: AioSession
    ) -> None:
        fake_resource = {
            "Type": "AWS::Lambda::Function",
            "Properties": {"FunctionName": "brand-new-func"},
        }

        with patch(
            "aws.live_events.processors.aws_lambda.LambdaFunctionExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)

            event = _lambda_event("CreateFunction20150331", "brand-new-func")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == [fake_resource]
        assert result.deleted_raw_results == []

    # -----------------------------------------------------------------------
    # Lambda deleted → delete correctness
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_lambda_deleted_returns_delete_result(
        self, processor: LambdaLiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch("aws.live_events.processors.aws_lambda.LambdaFunctionExporter") as MockExporter:
            event = _lambda_event("DeleteFunction20150331", "old-func")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)
            # Exporter should NOT be called on delete
            MockExporter.return_value.get_resource.assert_not_called()

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["Properties"]["FunctionName"] == "old-func"

    # -----------------------------------------------------------------------
    # Resilience
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_missing_function_name_returns_empty(
        self, processor: LambdaLiveEventProcessor, mock_session: AioSession
    ) -> None:
        event = make_eventbridge_event(
            _DETAIL_TYPE,
            {
                "eventSource": "lambda.amazonaws.com",
                "eventName": "CreateFunction20150331",
                "requestParameters": {},
            },
        )
        result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_exporter_exception_returns_empty(
        self, processor: LambdaLiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch(
            "aws.live_events.processors.aws_lambda.LambdaFunctionExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(
                side_effect=Exception("Lambda API error")
            )

            event = _lambda_event("UpdateFunctionConfiguration20150331v2", "err-func")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
