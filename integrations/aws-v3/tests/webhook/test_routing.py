from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aws.webhook.events import SNS_MESSAGE_TYPE_HEADER, SnsMessageType
from aws.webhook.processors.ec2_instance import EC2InstanceWebhookProcessor
from aws.webhook.processors.ecs_service import ECSServiceWebhookProcessor
from aws.webhook.processors.lambda_function import LambdaFunctionWebhookProcessor
from aws.webhook.processors.s3_bucket import S3BucketWebhookProcessor
from aws.webhook.processors.sns_subscription import (
    SnsSubscriptionConfirmationProcessor,
)
from tests.webhook.conftest import make_sns_notification, make_webhook_event


def _ec2_envelope() -> dict:
    return {
        "detail-type": "EC2 Instance State-change Notification",
        "account": "111111111111",
        "region": "us-east-1",
        "detail": {"instance-id": "i-1", "state": "running"},
    }


def _s3_envelope() -> dict:
    return {
        "detail-type": "AWS API Call via CloudTrail",
        "account": "111111111111",
        "region": "us-east-1",
        "detail": {
            "eventSource": "s3.amazonaws.com",
            "eventName": "CreateBucket",
            "requestParameters": {"bucketName": "b"},
        },
    }


def _lambda_envelope() -> dict:
    return {
        "detail-type": "AWS API Call via CloudTrail",
        "account": "111111111111",
        "region": "us-east-1",
        "detail": {
            "eventSource": "lambda.amazonaws.com",
            "eventName": "CreateFunction20150331",
            "requestParameters": {"functionName": "f"},
        },
    }


def _ecs_envelope() -> dict:
    return {
        "detail-type": "ECS Deployment State Change",
        "account": "111111111111",
        "region": "us-east-1",
        "resources": [
            "arn:aws:ecs:us-east-1:111111111111:service/checkout/billing"
        ],
        "detail": {
            "eventName": "SERVICE_DEPLOYMENT_IN_PROGRESS",
            "clusterArn": "arn:aws:ecs:us-east-1:111111111111:cluster/checkout",
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "envelope, matching_cls, non_matching_classes",
    [
        (
            _ec2_envelope(),
            EC2InstanceWebhookProcessor,
            [
                S3BucketWebhookProcessor,
                LambdaFunctionWebhookProcessor,
                ECSServiceWebhookProcessor,
            ],
        ),
        (
            _s3_envelope(),
            S3BucketWebhookProcessor,
            [
                EC2InstanceWebhookProcessor,
                LambdaFunctionWebhookProcessor,
                ECSServiceWebhookProcessor,
            ],
        ),
        (
            _lambda_envelope(),
            LambdaFunctionWebhookProcessor,
            [
                EC2InstanceWebhookProcessor,
                S3BucketWebhookProcessor,
                ECSServiceWebhookProcessor,
            ],
        ),
        (
            _ecs_envelope(),
            ECSServiceWebhookProcessor,
            [
                EC2InstanceWebhookProcessor,
                S3BucketWebhookProcessor,
                LambdaFunctionWebhookProcessor,
            ],
        ),
    ],
)
async def test_only_matching_processor_claims_event(
    envelope, matching_cls, non_matching_classes
) -> None:
    payload = make_sns_notification(envelope)
    event = make_webhook_event(payload)

    assert await matching_cls(event=event).should_process_event(event) is True
    for cls in non_matching_classes:
        assert await cls(event=event).should_process_event(event) is False


@pytest.mark.asyncio
async def test_unknown_detail_type_is_skipped_by_all_processors() -> None:
    payload = make_sns_notification(
        {"detail-type": "Mystery Event", "account": "1", "region": "us-east-1", "detail": {}}
    )
    event = make_webhook_event(payload)
    for cls in (
        EC2InstanceWebhookProcessor,
        S3BucketWebhookProcessor,
        LambdaFunctionWebhookProcessor,
        ECSServiceWebhookProcessor,
    ):
        assert await cls(event=event).should_process_event(event) is False


@pytest.mark.asyncio
async def test_invalid_signature_rejects_authentication(reject_sns_verifier) -> None:
    payload = make_sns_notification(_ec2_envelope())
    event = make_webhook_event(payload)
    processor = EC2InstanceWebhookProcessor(event=event)
    assert (
        await processor.authenticate(payload, event.headers) is False
    )


@pytest.mark.asyncio
async def test_valid_signature_accepts_authentication(stub_sns_verifier) -> None:
    payload = make_sns_notification(_ec2_envelope())
    event = make_webhook_event(payload)
    processor = EC2InstanceWebhookProcessor(event=event)
    assert (
        await processor.authenticate(payload, event.headers) is True
    )


@pytest.mark.asyncio
async def test_duplicate_event_short_circuits(stub_session_resolver) -> None:
    payload = make_sns_notification(_ec2_envelope(), message_id="dup-1")
    event = make_webhook_event(payload)
    processor = EC2InstanceWebhookProcessor(event=event)

    mock_exporter = AsyncMock()
    mock_exporter.get_resource = AsyncMock(
        return_value={"Type": "AWS::EC2::Instance", "Properties": {"InstanceId": "i-1"}}
    )
    with patch(
        "aws.webhook.processors.ec2_instance.EC2InstanceWebhookProcessor.exporter_cls",
        return_value=mock_exporter,
    ):
        first = await processor.handle_event(payload, resource=None)
        second = await processor.handle_event(payload, resource=None)

    assert len(first.updated_raw_results) == 1
    # Duplicate delivery must produce no upsert and no delete.
    assert second.updated_raw_results == []
    assert second.deleted_raw_results == []
    # Exporter should only have been hit once.
    assert mock_exporter.get_resource.call_count == 1


@pytest.mark.asyncio
async def test_subscription_confirmation_handled_by_dedicated_processor(stub_sns_verifier) -> None:
    payload = {
        "Type": SnsMessageType.SUBSCRIPTION_CONFIRMATION.value,
        "MessageId": "sub-1",
        "TopicArn": "arn:aws:sns:us-east-1:111111111111:port-aws-v3-live-events",
        "SubscribeURL": "https://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription&Token=abc",
        "Timestamp": "2026-05-14T12:00:00Z",
        "Signature": "x",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
        "SignatureVersion": "1",
    }
    event = make_webhook_event(payload)
    event.headers[SNS_MESSAGE_TYPE_HEADER] = SnsMessageType.SUBSCRIPTION_CONFIRMATION.value
    processor = SnsSubscriptionConfirmationProcessor(event=event)

    assert await processor.should_process_event(event) is True
    assert await processor.validate_payload(payload) is True

    # No other processor claims subscription confirmations.
    for cls in (
        EC2InstanceWebhookProcessor,
        S3BucketWebhookProcessor,
        LambdaFunctionWebhookProcessor,
        ECSServiceWebhookProcessor,
    ):
        assert await cls(event=event).should_process_event(event) is False
