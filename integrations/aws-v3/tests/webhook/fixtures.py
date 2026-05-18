"""Canned EventBridge envelopes for the AWS-V3 live-event processors.

Each fixture mirrors what the AWS docs publish for that event type so a
reader can correlate the code path with the upstream spec without having
to look up the schema separately.
"""

from __future__ import annotations

from typing import Any


def _envelope_base(source: str, detail_type: str, region: str) -> dict[str, Any]:
    return {
        "version": "0",
        "id": "00000000-0000-0000-0000-000000000000",
        "detail-type": detail_type,
        "source": source,
        "account": "123456789012",
        "time": "2026-05-14T12:00:00Z",
        "region": region,
        "resources": [],
    }


def ec2_state_change_event(instance_id: str, state: str) -> dict[str, Any]:
    """Native `aws.ec2` instance state-change envelope."""
    payload = _envelope_base(
        "aws.ec2", "EC2 Instance State-change Notification", "us-east-1"
    )
    payload["detail"] = {"instance-id": instance_id, "state": state}
    payload["resources"] = [
        f"arn:aws:ec2:us-east-1:123456789012:instance/{instance_id}"
    ]
    return payload


def ecs_service_action_event(
    cluster: str, service: str, event_name: str
) -> dict[str, Any]:
    """`ECS Service Action` envelope (e.g. SERVICE_STEADY_STATE, SERVICE_DELETED)."""
    payload = _envelope_base("aws.ecs", "ECS Service Action", "us-east-1")
    payload["resources"] = [
        f"arn:aws:ecs:us-east-1:123456789012:service/{cluster}/{service}"
    ]
    payload["detail"] = {
        "eventType": "INFO",
        "eventName": event_name,
        "clusterArn": f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
        "createdAt": "2026-05-14T12:00:00Z",
    }
    return payload


def ecs_deployment_state_change_event(
    cluster: str, service: str, event_name: str
) -> dict[str, Any]:
    """`ECS Deployment State Change` envelope (different `detail` shape)."""
    payload = _envelope_base("aws.ecs", "ECS Deployment State Change", "us-east-1")
    payload["resources"] = [
        f"arn:aws:ecs:us-east-1:123456789012:service/{cluster}/{service}"
    ]
    payload["detail"] = {
        "eventType": "INFO",
        "eventName": event_name,
        "deploymentId": "ecs-svc/1234567890123456789",
        "updatedAt": "2026-05-14T12:00:00Z",
        "reason": "ECS deployment ecs-svc/... in progress.",
    }
    return payload


def lambda_event(
    function_name: str, event_name: str, region: str = "us-east-1"
) -> dict[str, Any]:
    """CloudTrail-on-EventBridge envelope for a Lambda management action."""
    payload = _envelope_base("aws.lambda", "AWS API Call via CloudTrail", region)
    payload["detail"] = {
        "eventVersion": "1.08",
        "eventSource": "lambda.amazonaws.com",
        "eventName": event_name,
        "awsRegion": region,
        "requestParameters": {"functionName": function_name},
        "responseElements": {
            "functionArn": f"arn:aws:lambda:{region}:123456789012:function:{function_name}",
        },
    }
    return payload


def s3_create_bucket_event(
    bucket_name: str, location_constraint: str | None = None
) -> dict[str, Any]:
    """CloudTrail-on-EventBridge `CreateBucket` envelope (us-east-1 by AWS contract)."""
    payload = _envelope_base("aws.s3", "AWS API Call via CloudTrail", "us-east-1")
    request_params: dict[str, Any] = {"bucketName": bucket_name}
    if location_constraint is not None:
        request_params["CreateBucketConfiguration"] = {
            "LocationConstraint": location_constraint
        }
    payload["detail"] = {
        "eventVersion": "1.08",
        "eventSource": "s3.amazonaws.com",
        "eventName": "CreateBucket",
        "awsRegion": "us-east-1",
        "requestParameters": request_params,
    }
    return payload


def s3_delete_bucket_event(bucket_name: str) -> dict[str, Any]:
    payload = _envelope_base("aws.s3", "AWS API Call via CloudTrail", "us-east-1")
    payload["detail"] = {
        "eventVersion": "1.08",
        "eventSource": "s3.amazonaws.com",
        "eventName": "DeleteBucket",
        "awsRegion": "us-east-1",
        "requestParameters": {"bucketName": bucket_name},
    }
    return payload
