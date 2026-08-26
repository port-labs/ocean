from dataclasses import dataclass
from typing import Any, Generator, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from aws.core.helpers.metadata.types import ExporterMetadata, LiveEventFactories
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.webhook.cloudtrail_parser import parse_cloudtrail_event
from aws.webhook.consts import LIVE_EVENTS_API_KEY_HEADER
from aws.webhook.webhook_processors.cloudtrail_webhook_processor import (
    CloudTrailWebhookProcessor,
)

MODULE = "aws.webhook.webhook_processors.cloudtrail_webhook_processor"


@dataclass
class _LiveEventMetadataFixture:
    metadata: ExporterMetadata
    exporter_cls: MagicMock


def _live_event_metadata(
    exporter_cls: MagicMock | None = None,
) -> _LiveEventMetadataFixture:
    mock_exporter = AsyncMock()
    mock_exporter.get_resource = AsyncMock()
    exporter = exporter_cls or MagicMock(return_value=mock_exporter)
    live_events = LiveEventFactories(
        request_factory=MagicMock(),
        deletion_identifier_properties_factory=MagicMock(),
    )
    metadata = ExporterMetadata(
        exporter=cast(type[IResourceExporter[Any]], exporter),
        paginated_request_model=MagicMock(),
        live_events=live_events,
    )
    return _LiveEventMetadataFixture(metadata=metadata, exporter_cls=exporter)


def _create_event(bucket_name: str = "my-bucket") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "CreateBucket",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"bucketName": bucket_name},
        },
    }


def _lambda_create_event(function_name: str = "my-function") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "CreateFunction20150331",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"functionName": function_name},
        },
    }


def _lambda_delete_event(function_name: str = "my-function") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "DeleteFunction20150331",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"functionName": function_name},
        },
    }


def _dynamodb_create_event(table_name: str = "my-table") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "CreateTable",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"tableName": table_name},
        },
    }


def _dynamodb_delete_event(table_name: str = "my-table") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "DeleteTable",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"tableName": table_name},
        },
    }


def _rds_create_event(db_instance_identifier: str = "my-db-instance") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "CreateDBInstance",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"dbInstanceIdentifier": db_instance_identifier},
        },
    }


def _rds_delete_event(db_instance_identifier: str = "my-db-instance") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "DeleteDBInstance",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"dbInstanceIdentifier": db_instance_identifier},
        },
    }


def _delete_event(bucket_name: str = "my-bucket") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "DeleteBucket",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"bucketName": bucket_name},
        },
    }


@pytest.fixture(autouse=True)
def _live_events_feature_flag_enabled() -> Generator[None, None, None]:
    with patch(
        f"{MODULE}.is_aws_v3_live_events_enabled", new=AsyncMock(return_value=True)
    ):
        yield


@pytest.fixture
def processor() -> CloudTrailWebhookProcessor:
    return CloudTrailWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.mark.asyncio
async def test_should_process_event_true_for_create(
    processor: CloudTrailWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_create_event(), headers={})
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_false_for_unsupported_event_name(
    processor: CloudTrailWebhookProcessor,
) -> None:
    payload = _create_event()
    payload["detail"]["eventName"] = "PutBucketTagging"
    event = WebhookEvent(trace_id="t", payload=payload, headers={})
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds_returns_s3_bucket(
    processor: CloudTrailWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_create_event(), headers={})
    assert await processor.get_matching_kinds(event) == [ObjectKind.S3_BUCKET]


@pytest.mark.asyncio
async def test_authenticate_fails_when_feature_flag_disabled(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with patch(
        f"{MODULE}.is_aws_v3_live_events_enabled", new=AsyncMock(return_value=False)
    ):
        result = await processor.authenticate(
            {}, {LIVE_EVENTS_API_KEY_HEADER: "secret"}
        )
    assert result is False


@pytest.mark.asyncio
async def test_authenticate_succeeds_with_matching_api_key(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with (
        patch(
            f"{MODULE}.is_aws_v3_live_events_enabled", new=AsyncMock(return_value=True)
        ),
        patch(f"{MODULE}.get_live_events_api_key", return_value="secret"),
    ):
        result = await processor.authenticate(
            {}, {LIVE_EVENTS_API_KEY_HEADER: "secret"}
        )
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_fails_with_wrong_api_key(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with (
        patch(
            f"{MODULE}.is_aws_v3_live_events_enabled", new=AsyncMock(return_value=True)
        ),
        patch(f"{MODULE}.get_live_events_api_key", return_value="secret"),
    ):
        result = await processor.authenticate({}, {LIVE_EVENTS_API_KEY_HEADER: "wrong"})
    assert result is False


@pytest.mark.asyncio
async def test_authenticate_fails_when_not_configured(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with (
        patch(
            f"{MODULE}.is_aws_v3_live_events_enabled", new=AsyncMock(return_value=True)
        ),
        patch(f"{MODULE}.get_live_events_api_key", return_value=None),
    ):
        result = await processor.authenticate(
            {}, {LIVE_EVENTS_API_KEY_HEADER: "anything"}
        )
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_true_for_supported_event(
    processor: CloudTrailWebhookProcessor,
) -> None:
    assert await processor.validate_payload(_create_event()) is True


@pytest.mark.asyncio
async def test_validate_payload_false_for_malformed_payload(
    processor: CloudTrailWebhookProcessor,
) -> None:
    assert await processor.validate_payload({}) is False


@pytest.mark.asyncio
async def test_parse_cloudtrail_event_called_once_per_processor(
    processor: CloudTrailWebhookProcessor,
) -> None:
    payload = _delete_event()
    event = WebhookEvent(trace_id="t", payload=payload, headers={})

    with patch(
        f"{MODULE}.parse_cloudtrail_event", wraps=parse_cloudtrail_event
    ) as mock_parse:
        assert await processor.get_matching_kinds(event) == [ObjectKind.S3_BUCKET]
        assert await processor.validate_payload(payload) is True
        await processor.handle_event(payload, None)

    assert mock_parse.call_count == 1


@pytest.mark.asyncio
async def test_handle_event_delete_returns_deleted_result(
    processor: CloudTrailWebhookProcessor,
) -> None:
    result = await processor.handle_event(_delete_event("bucket-to-delete"), None)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {
            "Type": ObjectKind.S3_BUCKET,
            "Properties": {
                "Arn": "arn:aws:s3:::bucket-to-delete",
                "BucketName": "bucket-to-delete",
            },
        }
    ]


@pytest.mark.asyncio
async def test_handle_event_create_fetches_and_returns_resource(
    processor: CloudTrailWebhookProcessor,
) -> None:
    fake_resource = {
        "Type": ObjectKind.S3_BUCKET,
        "Properties": {"BucketName": "my-bucket"},
    }

    fixture = _live_event_metadata()
    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(
            f"{MODULE}.kind_to_export_metadata",
            {ObjectKind.S3_BUCKET: fixture.metadata},
        ),
    ):
        mock_exporter = fixture.exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(return_value=fake_resource)

        result = await processor.handle_event(_create_event(), None)

    fixture.exporter_cls.assert_called_once_with("session")
    assert result.updated_raw_results == [fake_resource]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_create_skips_when_no_session_found(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with patch(f"{MODULE}.get_session_for_account", new=AsyncMock(return_value=None)):
        result = await processor.handle_event(_create_event(), None)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_get_matching_kinds_returns_lambda_function(
    processor: CloudTrailWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_lambda_create_event(), headers={})
    assert await processor.get_matching_kinds(event) == [ObjectKind.LAMBDA_FUNCTION]


@pytest.mark.asyncio
async def test_handle_event_lambda_delete_returns_deleted_result(
    processor: CloudTrailWebhookProcessor,
) -> None:
    result = await processor.handle_event(
        _lambda_delete_event("function-to-delete"), None
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {
            "Type": ObjectKind.LAMBDA_FUNCTION,
            "Properties": {
                "FunctionArn": (
                    "arn:aws:lambda:us-east-1:111122223333:function:function-to-delete"
                ),
                "FunctionName": "function-to-delete",
            },
        }
    ]


@pytest.mark.asyncio
async def test_handle_event_lambda_create_fetches_and_returns_resource(
    processor: CloudTrailWebhookProcessor,
) -> None:
    fake_resource = {
        "Type": ObjectKind.LAMBDA_FUNCTION,
        "Properties": {"FunctionName": "my-function"},
    }

    fixture = _live_event_metadata()
    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(
            f"{MODULE}.kind_to_export_metadata",
            {ObjectKind.LAMBDA_FUNCTION: fixture.metadata},
        ),
    ):
        mock_exporter = fixture.exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(return_value=fake_resource)

        result = await processor.handle_event(_lambda_create_event(), None)

    fixture.exporter_cls.assert_called_once_with("session")
    assert result.updated_raw_results == [fake_resource]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_get_matching_kinds_returns_dynamodb_table(
    processor: CloudTrailWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_dynamodb_create_event(), headers={})
    assert await processor.get_matching_kinds(event) == [ObjectKind.DYNAMODB_TABLE]


@pytest.mark.asyncio
async def test_handle_event_dynamodb_delete_returns_deleted_result(
    processor: CloudTrailWebhookProcessor,
) -> None:
    result = await processor.handle_event(
        _dynamodb_delete_event("table-to-delete"), None
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {
            "Type": ObjectKind.DYNAMODB_TABLE,
            "Properties": {
                "TableArn": (
                    "arn:aws:dynamodb:us-east-1:111122223333:table/table-to-delete"
                ),
                "TableName": "table-to-delete",
            },
        }
    ]


@pytest.mark.asyncio
async def test_handle_event_dynamodb_create_fetches_and_returns_resource(
    processor: CloudTrailWebhookProcessor,
) -> None:
    fake_resource = {
        "Type": ObjectKind.DYNAMODB_TABLE,
        "Properties": {"TableName": "my-table"},
    }

    fixture = _live_event_metadata()
    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(
            f"{MODULE}.kind_to_export_metadata",
            {ObjectKind.DYNAMODB_TABLE: fixture.metadata},
        ),
    ):
        mock_exporter = fixture.exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(return_value=fake_resource)

        result = await processor.handle_event(_dynamodb_create_event(), None)

    fixture.exporter_cls.assert_called_once_with("session")
    assert result.updated_raw_results == [fake_resource]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_get_matching_kinds_returns_rds_db_instance(
    processor: CloudTrailWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_rds_create_event(), headers={})
    assert await processor.get_matching_kinds(event) == [ObjectKind.RDS_DB_INSTANCE]


@pytest.mark.asyncio
async def test_handle_event_rds_db_instance_delete_returns_deleted_result(
    processor: CloudTrailWebhookProcessor,
) -> None:
    result = await processor.handle_event(
        _rds_delete_event("db-instance-to-delete"), None
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {
            "Type": ObjectKind.RDS_DB_INSTANCE,
            "Properties": {
                "DBInstanceArn": (
                    "arn:aws:rds:us-east-1:111122223333:db:db-instance-to-delete"
                ),
                "DBInstanceIdentifier": "db-instance-to-delete",
            },
        }
    ]


@pytest.mark.asyncio
async def test_handle_event_rds_db_instance_create_fetches_and_returns_resource(
    processor: CloudTrailWebhookProcessor,
) -> None:
    fake_resource = {
        "Type": ObjectKind.RDS_DB_INSTANCE,
        "Properties": {"DBInstanceIdentifier": "my-db-instance"},
    }

    fixture = _live_event_metadata()
    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(
            f"{MODULE}.kind_to_export_metadata",
            {ObjectKind.RDS_DB_INSTANCE: fixture.metadata},
        ),
    ):
        mock_exporter = fixture.exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(return_value=fake_resource)

        result = await processor.handle_event(_rds_create_event(), None)

    fixture.exporter_cls.assert_called_once_with("session")
    assert result.updated_raw_results == [fake_resource]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_rds_db_instance_create_treats_not_found_as_deleted(
    processor: CloudTrailWebhookProcessor,
) -> None:
    class FakeNotFound(Exception):
        response = {"Error": {"Code": "DBInstanceNotFound"}}

    fixture = _live_event_metadata()
    assert fixture.metadata.live_events is not None
    cast(
        MagicMock,
        fixture.metadata.live_events.deletion_identifier_properties_factory,
    ).return_value = {
        "DBInstanceArn": (
            "arn:aws:rds:us-east-1:111122223333:db:missing-db-instance"
        ),
        "DBInstanceIdentifier": "missing-db-instance",
    }

    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(
            f"{MODULE}.kind_to_export_metadata",
            {ObjectKind.RDS_DB_INSTANCE: fixture.metadata},
        ),
    ):
        mock_exporter = fixture.exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(side_effect=FakeNotFound())

        result = await processor.handle_event(
            _rds_create_event("missing-db-instance"), None
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {
            "Type": ObjectKind.RDS_DB_INSTANCE,
            "Properties": {
                "DBInstanceArn": (
                    "arn:aws:rds:us-east-1:111122223333:db:missing-db-instance"
                ),
                "DBInstanceIdentifier": "missing-db-instance",
            },
        }
    ]


@pytest.mark.asyncio
async def test_handle_event_create_skips_access_denied(
    processor: CloudTrailWebhookProcessor,
) -> None:
    class FakeAccessDenied(Exception):
        response = {"Error": {"Code": "AccessDenied"}}

    fixture = _live_event_metadata()

    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(
            f"{MODULE}.kind_to_export_metadata",
            {ObjectKind.S3_BUCKET: fixture.metadata},
        ),
    ):
        mock_exporter = fixture.exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(side_effect=FakeAccessDenied())

        result = await processor.handle_event(_create_event("denied-bucket"), None)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_create_treats_not_found_as_deleted(
    processor: CloudTrailWebhookProcessor,
) -> None:
    class FakeNotFound(Exception):
        response = {"Error": {"Code": "NoSuchBucket"}}

    fixture = _live_event_metadata()
    assert fixture.metadata.live_events is not None
    cast(
        MagicMock,
        fixture.metadata.live_events.deletion_identifier_properties_factory,
    ).return_value = {
        "Arn": "arn:aws:s3:::missing-bucket",
        "BucketName": "missing-bucket",
    }

    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(
            f"{MODULE}.kind_to_export_metadata",
            {ObjectKind.S3_BUCKET: fixture.metadata},
        ),
    ):
        mock_exporter = fixture.exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(side_effect=FakeNotFound())

        result = await processor.handle_event(_create_event("missing-bucket"), None)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {
            "Type": ObjectKind.S3_BUCKET,
            "Properties": {
                "Arn": "arn:aws:s3:::missing-bucket",
                "BucketName": "missing-bucket",
            },
        }
    ]
