"""Tests for ``LambdaFunctionWebhookProcessor``."""

import json
from pathlib import Path
from typing import Any

import pytest
from unittest.mock import AsyncMock

from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.webhook.processors.lambda_function_processor import (
    LambdaFunctionWebhookProcessor,
)
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
async def test_update_function_code_emits_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CT-via-EB `UpdateFunctionCode20150331v2` envelope -> one call to
    `LambdaFunctionExporter.get_resource(...)` with `function_name=
    detail.requestParameters.functionName`."""

    payload = _load_fixture("lambda_update_function_code.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock(return_value={"Type": "AWS::Lambda::Function"})

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(LambdaFunctionWebhookProcessor, "_exporter_cls", _Exporter)
    proc = LambdaFunctionWebhookProcessor(event)

    async def _sess(account_id: str) -> Any:
        return object()

    monkeypatch.setattr(
        "aws.webhook.processors.aws_abstract_webhook_processor.get_session_for_account",
        _sess,
    )

    res = await proc.handle_event(payload, _RC())  # type: ignore[arg-type]
    assert res.deleted_raw_results == []
    assert res.updated_raw_results == [{"Type": "AWS::Lambda::Function"}]

    assert exporter_mock.call_count == 1
    (req,) = exporter_mock.call_args.args
    assert isinstance(req, SingleLambdaFunctionRequest)
    assert req.function_name == "my-function"


@pytest.mark.asyncio
async def test_delete_function_emits_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CT-via-EB `DeleteFunction20150331` envelope -> no exporter call;
    emit a delete stub keyed on the reconstructed function ARN."""

    payload = _load_fixture("lambda_delete_function.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock()

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(LambdaFunctionWebhookProcessor, "_exporter_cls", _Exporter)
    proc = LambdaFunctionWebhookProcessor(event)

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
            "Type": "AWS::Lambda::Function",
            "Properties": {
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
                "FunctionName": "my-function",
            },
            "__ExtraContext": {"AccountId": "123456789012", "Region": "us-east-1"},
        }
    ]
