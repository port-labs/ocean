from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from aws_integration.overrides import AWSCustomKindResourceConfig
from aws.core.exporters.cloudcontrol.resource.models import (
    SingleCloudControlResourceRequest,
)
from aws.core.helpers.types import ObjectKind
from aws.webhook.webhook_processors.input_transformer_webhook_processor import (
    InputTransformerWebhookProcessor,
)

BASE_MODULE = "aws.webhook.webhook_processors.live_events_webhook_processor"
CLOUD_CONTROL_EXPORTER = (
    "aws.core.exporters.cloudcontrol.resource.metadata.CloudControlExporter"
)

_ACCOUNT_ID = "111122223333"
_REGION = "us-east-1"
_ROLE_KIND = "AWS::IAM::Role"


def _payload(
    resource_type: str = _ROLE_KIND, identifier: str = "my-role"
) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "identifier": identifier,
        "accountId": _ACCOUNT_ID,
        "awsRegion": _REGION,
        "eventName": "CreateRole",
    }


def _custom_kind_config(kind: str = _ROLE_KIND) -> AWSCustomKindResourceConfig:
    return AWSCustomKindResourceConfig.parse_obj(
        {
            "kind": kind,
            "selector": {"query": "true"},
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".Properties.Identifier",
                        "blueprint": '"awsRole"',
                    }
                }
            },
        }
    )


def _deleted_raw_result(identifier: str) -> dict[str, Any]:
    return {
        "Type": _ROLE_KIND,
        "Properties": {"Identifier": identifier},
        "__ExtraContext": {"AccountId": _ACCOUNT_ID, "Region": _REGION},
    }


@pytest.fixture
def processor() -> InputTransformerWebhookProcessor:
    return InputTransformerWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.fixture
def cloud_control_exporter() -> Any:
    with patch(CLOUD_CONTROL_EXPORTER) as exporter_cls:
        exporter_cls.return_value.get_resource = AsyncMock()
        yield exporter_cls


@pytest.fixture
def session() -> Any:
    with patch(
        f"{BASE_MODULE}.get_session_for_account",
        new=AsyncMock(return_value="session"),
    ) as get_session:
        yield get_session


@pytest.mark.asyncio
async def test_should_process_event_true_for_transformed_payload(
    processor: InputTransformerWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_payload(), headers={})
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_false_for_raw_cloudtrail_payload(
    processor: InputTransformerWebhookProcessor,
) -> None:
    payload = {
        "account": _ACCOUNT_ID,
        "region": _REGION,
        "detail": {"eventName": "CreateBucket", "eventSource": "s3.amazonaws.com"},
    }
    event = WebhookEvent(trace_id="t", payload=payload, headers={})
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds_returns_resource_type(
    processor: InputTransformerWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_payload(), headers={})
    assert await processor.get_matching_kinds(event) == [_ROLE_KIND]


@pytest.mark.asyncio
async def test_validate_payload_false_when_identifier_missing(
    processor: InputTransformerWebhookProcessor,
) -> None:
    assert await processor.validate_payload(_payload(identifier="")) is False


@pytest.mark.asyncio
async def test_handle_event_custom_kind_fetches_via_cloud_control(
    processor: InputTransformerWebhookProcessor,
    cloud_control_exporter: MagicMock,
    session: AsyncMock,
) -> None:
    fake_resource = {"Type": _ROLE_KIND, "Properties": {"Identifier": "my-role"}}
    cloud_control_exporter.return_value.get_resource.return_value = fake_resource

    result = await processor.handle_event(_payload(), _custom_kind_config())

    cloud_control_exporter.assert_called_once_with("session")
    cloud_control_exporter.return_value.get_resource.assert_awaited_once_with(
        SingleCloudControlResourceRequest(
            type_name=_ROLE_KIND,
            identifier="my-role",
            region=_REGION,
            account_id=_ACCOUNT_ID,
            include=[],
        )
    )
    assert result.updated_raw_results == [fake_resource]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_custom_kind_treats_not_found_as_deleted(
    processor: InputTransformerWebhookProcessor,
    cloud_control_exporter: MagicMock,
    session: AsyncMock,
) -> None:
    class FakeNotFound(Exception):
        response = {"Error": {"Code": "ResourceNotFoundException"}}

    cloud_control_exporter.return_value.get_resource.side_effect = FakeNotFound()

    result = await processor.handle_event(
        _payload(identifier="deleted-role"), _custom_kind_config()
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [_deleted_raw_result("deleted-role")]


@pytest.mark.asyncio
async def test_handle_event_custom_kind_skips_access_denied(
    processor: InputTransformerWebhookProcessor,
    cloud_control_exporter: MagicMock,
    session: AsyncMock,
) -> None:
    class FakeAccessDenied(Exception):
        response = {"Error": {"Code": "AccessDeniedException"}}

    cloud_control_exporter.return_value.get_resource.side_effect = FakeAccessDenied()

    result = await processor.handle_event(_payload(), _custom_kind_config())

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_skips_when_no_session_found(
    processor: InputTransformerWebhookProcessor,
    cloud_control_exporter: MagicMock,
) -> None:
    with patch(
        f"{BASE_MODULE}.get_session_for_account", new=AsyncMock(return_value=None)
    ):
        result = await processor.handle_event(_payload(), _custom_kind_config())

    cloud_control_exporter.assert_not_called()
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_skips_unknown_kind_without_custom_config(
    processor: InputTransformerWebhookProcessor,
    cloud_control_exporter: MagicMock,
    session: AsyncMock,
) -> None:
    result = await processor.handle_event(_payload(), None)

    cloud_control_exporter.assert_not_called()
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_built_in_kind_uses_its_exporter(
    processor: InputTransformerWebhookProcessor,
    cloud_control_exporter: MagicMock,
    session: AsyncMock,
) -> None:
    fake_resource = {
        "Type": ObjectKind.S3_BUCKET,
        "Properties": {"BucketName": "my-bucket"},
    }
    with patch(
        "aws.core.exporters.s3.bucket.exporter.S3BucketExporter.get_resource",
        new=AsyncMock(return_value=fake_resource),
    ) as get_resource:
        result = await processor.handle_event(
            _payload(resource_type=ObjectKind.S3_BUCKET, identifier="my-bucket"),
            None,
        )

    get_resource.assert_awaited_once()
    cloud_control_exporter.assert_not_called()
    assert result.updated_raw_results == [fake_resource]
