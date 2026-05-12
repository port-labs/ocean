"""Tests for ``S3BucketWebhookProcessor``."""

import json
from pathlib import Path
from typing import Any

import pytest
from unittest.mock import AsyncMock

from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.webhook.processors.s3_bucket_processor import S3BucketWebhookProcessor
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
async def test_create_bucket_emits_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CT-via-EB `CreateBucket` envelope -> one call to
    `S3BucketExporter.get_resource(...)` with `bucket_name=
    detail.requestParameters.bucketName`."""

    payload = _load_fixture("s3_create_bucket.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock(return_value={"Type": "AWS::S3::Bucket"})

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(S3BucketWebhookProcessor, "_exporter_cls", _Exporter)
    proc = S3BucketWebhookProcessor(event)

    async def _sess(account_id: str) -> Any:
        return object()

    monkeypatch.setattr(
        "aws.webhook.processors.aws_abstract_webhook_processor.get_session_for_account",
        _sess,
    )

    res = await proc.handle_event(payload, _RC())  # type: ignore[arg-type]
    assert res.deleted_raw_results == []
    assert res.updated_raw_results == [{"Type": "AWS::S3::Bucket"}]

    assert exporter_mock.call_count == 1
    (req,) = exporter_mock.call_args.args
    assert isinstance(req, SingleBucketRequest)
    assert req.bucket_name == "my-test-bucket"


@pytest.mark.asyncio
async def test_delete_bucket_emits_delete_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CT-via-EB `DeleteBucket` envelope -> no exporter call; emit a
    delete stub with `Properties.Arn = "arn:aws:s3:::<bucket_name>"`."""

    payload = _load_fixture("s3_delete_bucket.json")
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    exporter_mock = AsyncMock()

    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        get_resource = exporter_mock

    monkeypatch.setattr(S3BucketWebhookProcessor, "_exporter_cls", _Exporter)
    proc = S3BucketWebhookProcessor(event)

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
            "Type": "AWS::S3::Bucket",
            "Properties": {
                "Arn": "arn:aws:s3:::my-test-bucket",
                "BucketName": "my-test-bucket",
            },
            "__ExtraContext": {"AccountId": "123456789012", "Region": "us-east-1"},
        }
    ]
