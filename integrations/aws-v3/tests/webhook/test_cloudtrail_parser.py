from typing import cast

from aws.core.helpers.types import ObjectKind
from aws.webhook.cloudtrail_parser import (
    CloudTrailDetail,
    CloudTrailEventAction,
    EventBridgeCloudTrailPayload,
    is_supported_cloudtrail_event,
    parse_cloudtrail_event,
)


def _eventbridge_envelope(
    event_name: str,
    bucket_name: str | None = "my-bucket",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "s3.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if bucket_name is not None:
        detail["requestParameters"] = {"bucketName": bucket_name}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {
        "detail": detail,
    }
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.s3",
        },
    )


def test_is_supported_cloudtrail_event_true_for_create() -> None:
    payload = _eventbridge_envelope("CreateBucket")
    assert is_supported_cloudtrail_event(payload) is True


def test_is_supported_cloudtrail_event_true_for_delete() -> None:
    payload = _eventbridge_envelope("DeleteBucket")
    assert is_supported_cloudtrail_event(payload) is True


def test_is_supported_cloudtrail_event_false_for_unsupported_event() -> None:
    payload = _eventbridge_envelope("PutBucketTagging")
    assert is_supported_cloudtrail_event(payload) is False


def test_is_supported_cloudtrail_event_false_for_malformed_payload() -> None:
    assert is_supported_cloudtrail_event({}) is False
    assert (
        is_supported_cloudtrail_event(
            cast(EventBridgeCloudTrailPayload, {"detail": "not-a-dict"})
        )
        is False
    )


def test_is_supported_cloudtrail_event_false_when_error_code_present() -> None:
    payload = _eventbridge_envelope("DeleteBucket")
    payload["detail"]["errorCode"] = "AccessDenied"
    assert is_supported_cloudtrail_event(payload) is False


def test_parse_returns_none_when_error_code_present() -> None:
    payload = _eventbridge_envelope("DeleteBucket")
    payload["detail"]["errorCode"] = "BucketNotEmpty"
    payload["detail"]["errorMessage"] = "The bucket you tried to delete is not empty"
    assert parse_cloudtrail_event(payload) is None


def test_parse_create_bucket_event() -> None:
    payload = _eventbridge_envelope("CreateBucket", bucket_name="my-bucket")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.S3_BUCKET
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "my-bucket"
    assert parsed.account_id == "111122223333"
    assert parsed.region == "us-east-1"
    assert parsed.event_name == "CreateBucket"


def test_parse_delete_bucket_event() -> None:
    payload = _eventbridge_envelope("DeleteBucket", bucket_name="my-bucket")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.action == CloudTrailEventAction.DELETE


def test_parse_returns_none_for_unsupported_event() -> None:
    payload = _eventbridge_envelope("PutBucketTagging")
    assert parse_cloudtrail_event(payload) is None


def test_parse_returns_none_when_bucket_name_missing() -> None:
    payload = _eventbridge_envelope("CreateBucket", bucket_name=None)
    assert parse_cloudtrail_event(payload) is None


def test_parse_returns_none_when_account_missing() -> None:
    payload = _eventbridge_envelope("CreateBucket", account=None)
    assert parse_cloudtrail_event(payload) is None


def test_parse_falls_back_to_detail_recipient_account_id() -> None:
    payload = _eventbridge_envelope("CreateBucket")
    del payload["account"]

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.account_id == "111122223333"


def _lambda_eventbridge_envelope(
    event_name: str,
    function_name: str | None = "my-function",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "lambda.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if function_name is not None:
        detail["requestParameters"] = {"functionName": function_name}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {
        "detail": detail,
    }
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.lambda",
        },
    )


def test_is_supported_cloudtrail_event_true_for_create_function() -> None:
    payload = _lambda_eventbridge_envelope("CreateFunction20150331")
    assert is_supported_cloudtrail_event(payload) is True


def test_is_supported_cloudtrail_event_true_for_delete_function() -> None:
    payload = _lambda_eventbridge_envelope("DeleteFunction20150331")
    assert is_supported_cloudtrail_event(payload) is True


def test_is_supported_cloudtrail_event_false_for_unversioned_lambda_names() -> None:
    for event_name in (
        "CreateFunction",
        "DeleteFunction",
        "UpdateFunctionConfiguration",
        "UpdateFunctionCode",
    ):
        payload = _lambda_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is False


def test_parse_create_function_event() -> None:
    payload = _lambda_eventbridge_envelope(
        "CreateFunction20150331", function_name="my-function"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.LAMBDA_FUNCTION
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "my-function"
    assert parsed.event_name == "CreateFunction20150331"


def test_parse_update_function_configuration_event() -> None:
    payload = _lambda_eventbridge_envelope("UpdateFunctionConfiguration20150331v2")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.LAMBDA_FUNCTION
    assert parsed.action == CloudTrailEventAction.UPSERT


def test_parse_delete_function_event() -> None:
    payload = _lambda_eventbridge_envelope("DeleteFunction20150331")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.LAMBDA_FUNCTION
    assert parsed.action == CloudTrailEventAction.DELETE


def test_parse_returns_none_when_function_name_missing() -> None:
    payload = _lambda_eventbridge_envelope("CreateFunction20150331", function_name=None)
    assert parse_cloudtrail_event(payload) is None


def test_is_supported_cloudtrail_event_true_for_versioned_lambda_names() -> None:
    for event_name in (
        "CreateFunction20150331",
        "DeleteFunction20150331",
        "UpdateFunctionConfiguration20150331v2",
        "UpdateFunctionCode20150331v2",
    ):
        payload = _lambda_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_versioned_lambda_event_names() -> None:
    payload = _lambda_eventbridge_envelope(
        "DeleteFunction20150331", function_name="my-function"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.LAMBDA_FUNCTION
    assert parsed.action == CloudTrailEventAction.DELETE
    assert parsed.identifier == "my-function"
    assert parsed.event_name == "DeleteFunction20150331"


def test_is_supported_cloudtrail_event_false_for_unrelated_lambda_prefix() -> None:
    payload = _lambda_eventbridge_envelope("GetFunction20150331v2")
    assert is_supported_cloudtrail_event(payload) is False


def _dynamodb_eventbridge_envelope(
    event_name: str,
    table_name: str | None = "my-table",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "dynamodb.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if table_name is not None:
        detail["requestParameters"] = {"tableName": table_name}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.dynamodb",
        },
    )


def test_is_supported_cloudtrail_event_true_for_dynamodb_events() -> None:
    for event_name in ("CreateTable", "UpdateTable", "DeleteTable"):
        payload = _dynamodb_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_create_table_event() -> None:
    payload = _dynamodb_eventbridge_envelope("CreateTable", table_name="my-table")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.DYNAMODB_TABLE
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "my-table"
    assert parsed.event_name == "CreateTable"


def test_parse_delete_table_event() -> None:
    payload = _dynamodb_eventbridge_envelope("DeleteTable", table_name="my-table")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.DYNAMODB_TABLE
    assert parsed.action == CloudTrailEventAction.DELETE


def test_parse_returns_none_when_table_name_missing() -> None:
    payload = _dynamodb_eventbridge_envelope("CreateTable", table_name=None)
    assert parse_cloudtrail_event(payload) is None


def _rds_db_instance_eventbridge_envelope(
    event_name: str,
    db_instance_identifier: str | None = "my-db-instance",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
    identifier_key: str = "dbInstanceIdentifier",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "rds.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if db_instance_identifier is not None:
        detail["requestParameters"] = {identifier_key: db_instance_identifier}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.rds",
        },
    )


def test_is_supported_cloudtrail_event_true_for_rds_db_instance_events() -> None:
    for event_name in ("CreateDBInstance", "ModifyDBInstance", "DeleteDBInstance"):
        payload = _rds_db_instance_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_create_db_instance_event() -> None:
    payload = _rds_db_instance_eventbridge_envelope(
        "CreateDBInstance", db_instance_identifier="my-db-instance"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.RDS_DB_INSTANCE
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "my-db-instance"
    assert parsed.event_name == "CreateDBInstance"


def test_parse_modify_db_instance_event() -> None:
    payload = _rds_db_instance_eventbridge_envelope("ModifyDBInstance")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.RDS_DB_INSTANCE
    assert parsed.action == CloudTrailEventAction.UPSERT


def test_parse_delete_db_instance_event() -> None:
    payload = _rds_db_instance_eventbridge_envelope("DeleteDBInstance")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.RDS_DB_INSTANCE
    assert parsed.action == CloudTrailEventAction.DELETE


def test_parse_db_instance_identifier_from_d_b_instance_identifier_key() -> None:
    payload = _rds_db_instance_eventbridge_envelope(
        "DeleteDBInstance",
        db_instance_identifier="legacy-db",
        identifier_key="dBInstanceIdentifier",
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.identifier == "legacy-db"


def test_parse_returns_none_when_db_instance_identifier_missing() -> None:
    payload = _rds_db_instance_eventbridge_envelope(
        "CreateDBInstance", db_instance_identifier=None
    )
    assert parse_cloudtrail_event(payload) is None


def _cluster_eventbridge_envelope(
    event_name: str,
    *,
    event_source: str,
    cluster_name: str | None = "my-cluster",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
    identifier_key: str = "clusterName",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": event_source,
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if cluster_name is not None:
        detail["requestParameters"] = {identifier_key: cluster_name}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": event_source,
        },
    )


def _ecr_eventbridge_envelope(
    event_name: str,
    repository_name: str | None = "my-repo",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    return _cluster_eventbridge_envelope(
        event_name,
        event_source="ecr.amazonaws.com",
        cluster_name=repository_name,
        account=account,
        region=region,
        identifier_key="repositoryName",
    )


def test_is_supported_cloudtrail_event_true_for_ecr_repository_events() -> None:
    for event_name in ("CreateRepository", "DeleteRepository"):
        payload = _ecr_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_create_repository_event() -> None:
    payload = _ecr_eventbridge_envelope("CreateRepository", repository_name="my-repo")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.ECR_REPOSITORY
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "my-repo"
    assert parsed.event_name == "CreateRepository"


def test_parse_delete_repository_event() -> None:
    payload = _ecr_eventbridge_envelope("DeleteRepository")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.ECR_REPOSITORY
    assert parsed.action == CloudTrailEventAction.DELETE


def test_parse_returns_none_when_repository_name_missing() -> None:
    payload = _ecr_eventbridge_envelope("CreateRepository", repository_name=None)
    assert parse_cloudtrail_event(payload) is None


def test_is_supported_cloudtrail_event_true_for_ecs_cluster_events() -> None:
    for event_name in (
        "CreateCluster",
        "PutClusterCapacityProviders",
        "DeleteCluster",
    ):
        payload = _cluster_eventbridge_envelope(
            event_name, event_source="ecs.amazonaws.com"
        )
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_ecs_create_cluster_event() -> None:
    payload = _cluster_eventbridge_envelope(
        "CreateCluster", event_source="ecs.amazonaws.com", cluster_name="ecs-cluster"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.ECS_CLUSTER
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "ecs-cluster"


def test_parse_ecs_delete_cluster_event() -> None:
    payload = _cluster_eventbridge_envelope(
        "DeleteCluster", event_source="ecs.amazonaws.com"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.ECS_CLUSTER
    assert parsed.action == CloudTrailEventAction.DELETE


def test_parse_ecs_put_cluster_capacity_providers_event_from_cluster_name() -> None:
    payload = _cluster_eventbridge_envelope(
        "PutClusterCapacityProviders",
        event_source="ecs.amazonaws.com",
        cluster_name="ecs-cluster",
        identifier_key="cluster",
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.ECS_CLUSTER
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "ecs-cluster"


def test_parse_ecs_put_cluster_capacity_providers_event_from_cluster_arn() -> None:
    payload = _cluster_eventbridge_envelope(
        "PutClusterCapacityProviders",
        event_source="ecs.amazonaws.com",
        cluster_name="arn:aws:ecs:us-east-1:111122223333:cluster/ecs-cluster",
        identifier_key="cluster",
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.ECS_CLUSTER
    assert parsed.identifier == "ecs-cluster"


def test_is_supported_cloudtrail_event_true_for_eks_cluster_events() -> None:
    for event_name in (
        "CreateCluster",
        "UpdateClusterConfig",
        "UpdateClusterVersion",
        "DeleteCluster",
    ):
        payload = _cluster_eventbridge_envelope(
            event_name, event_source="eks.amazonaws.com"
        )
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_eks_create_cluster_event_from_cluster_name() -> None:
    payload = _cluster_eventbridge_envelope(
        "CreateCluster", event_source="eks.amazonaws.com", cluster_name="eks-cluster"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.EKS_CLUSTER
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "eks-cluster"


def test_parse_eks_create_cluster_event_from_name() -> None:
    payload = _cluster_eventbridge_envelope(
        "CreateCluster",
        event_source="eks.amazonaws.com",
        cluster_name="eks-cluster",
        identifier_key="name",
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.EKS_CLUSTER
    assert parsed.identifier == "eks-cluster"


def test_parse_eks_delete_cluster_event() -> None:
    payload = _cluster_eventbridge_envelope(
        "DeleteCluster", event_source="eks.amazonaws.com"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.EKS_CLUSTER
    assert parsed.action == CloudTrailEventAction.DELETE


def test_create_cluster_without_event_source_is_not_supported() -> None:
    payload = _cluster_eventbridge_envelope(
        "CreateCluster",
        event_source="ecs.amazonaws.com",
        cluster_name="ecs-cluster",
    )
    del payload["detail"]["eventSource"]

    assert is_supported_cloudtrail_event(payload) is False
    assert parse_cloudtrail_event(payload) is None


def test_ecs_and_eks_create_cluster_are_disambiguated_by_event_source() -> None:
    ecs_payload = _cluster_eventbridge_envelope(
        "CreateCluster", event_source="ecs.amazonaws.com", cluster_name="shared-name"
    )
    eks_payload = _cluster_eventbridge_envelope(
        "CreateCluster", event_source="eks.amazonaws.com", cluster_name="shared-name"
    )

    ecs_parsed = parse_cloudtrail_event(ecs_payload)
    eks_parsed = parse_cloudtrail_event(eks_payload)

    assert ecs_parsed is not None
    assert eks_parsed is not None
    assert ecs_parsed.kind == ObjectKind.ECS_CLUSTER
    assert eks_parsed.kind == ObjectKind.EKS_CLUSTER


def _rds_db_cluster_eventbridge_envelope(
    event_name: str,
    db_cluster_identifier: str | None = "my-db-cluster",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
    identifier_key: str = "dbClusterIdentifier",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "rds.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if db_cluster_identifier is not None:
        detail["requestParameters"] = {identifier_key: db_cluster_identifier}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.rds",
        },
    )


def test_is_supported_cloudtrail_event_true_for_rds_db_cluster_events() -> None:
    for event_name in ("CreateDBCluster", "ModifyDBCluster", "DeleteDBCluster"):
        payload = _rds_db_cluster_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_rds_db_cluster_events() -> None:
    create_payload = _rds_db_cluster_eventbridge_envelope("CreateDBCluster")
    delete_payload = _rds_db_cluster_eventbridge_envelope("DeleteDBCluster")

    create_parsed = parse_cloudtrail_event(create_payload)
    delete_parsed = parse_cloudtrail_event(delete_payload)

    assert create_parsed is not None
    assert create_parsed.kind == ObjectKind.RDS_DB_CLUSTER
    assert create_parsed.action == CloudTrailEventAction.UPSERT
    assert create_parsed.identifier == "my-db-cluster"

    assert delete_parsed is not None
    assert delete_parsed.kind == ObjectKind.RDS_DB_CLUSTER
    assert delete_parsed.action == CloudTrailEventAction.DELETE


def test_parse_db_cluster_identifier_from_d_b_cluster_identifier_key() -> None:
    payload = _rds_db_cluster_eventbridge_envelope(
        "DeleteDBCluster",
        db_cluster_identifier="legacy-cluster",
        identifier_key="dBClusterIdentifier",
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.identifier == "legacy-cluster"


def _sns_topic_eventbridge_envelope(
    event_name: str,
    *,
    topic_name: str | None = "my-topic",
    topic_arn: str | None = None,
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "sns.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account

    request_parameters: dict[str, str] = {}
    if topic_name is not None:
        request_parameters["name"] = topic_name
    if topic_arn is not None:
        request_parameters["topicArn"] = topic_arn
    detail["requestParameters"] = request_parameters

    if event_name == "CreateTopic" and topic_name is not None and account and region:
        detail["responseElements"] = {
            "topicArn": f"arn:aws:sns:{region}:{account}:{topic_name}"
        }

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.sns",
        },
    )


def test_is_supported_cloudtrail_event_true_for_sns_topic_events() -> None:
    for event_name in ("CreateTopic", "SetTopicAttributes", "DeleteTopic"):
        payload = _sns_topic_eventbridge_envelope(
            event_name,
            topic_name=None if event_name != "CreateTopic" else "my-topic",
            topic_arn=(
                "arn:aws:sns:us-east-1:111122223333:my-topic"
                if event_name != "CreateTopic"
                else None
            ),
        )
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_sns_topic_events() -> None:
    create_payload = _sns_topic_eventbridge_envelope("CreateTopic")
    delete_payload = _sns_topic_eventbridge_envelope(
        "DeleteTopic",
        topic_name=None,
        topic_arn="arn:aws:sns:us-east-1:111122223333:my-topic",
    )

    create_parsed = parse_cloudtrail_event(create_payload)
    delete_parsed = parse_cloudtrail_event(delete_payload)

    assert create_parsed is not None
    assert create_parsed.kind == ObjectKind.SNS_TOPIC
    assert create_parsed.action == CloudTrailEventAction.UPSERT
    assert create_parsed.identifier == "my-topic"

    assert delete_parsed is not None
    assert delete_parsed.kind == ObjectKind.SNS_TOPIC
    assert delete_parsed.action == CloudTrailEventAction.DELETE


def _sqs_queue_eventbridge_envelope(
    event_name: str,
    *,
    queue_name: str | None = "my-queue",
    queue_url: str | None = None,
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "sqs.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account

    request_parameters: dict[str, str] = {}
    if queue_name is not None:
        request_parameters["queueName"] = queue_name
    if queue_url is not None:
        request_parameters["queueUrl"] = queue_url
    detail["requestParameters"] = request_parameters

    if event_name == "CreateQueue" and queue_name is not None and account and region:
        detail["responseElements"] = {
            "queueUrl": f"https://sqs.{region}.amazonaws.com/{account}/{queue_name}"
        }

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.sqs",
        },
    )


def test_is_supported_cloudtrail_event_true_for_sqs_queue_events() -> None:
    for event_name in ("CreateQueue", "SetQueueAttributes", "DeleteQueue"):
        payload = _sqs_queue_eventbridge_envelope(
            event_name,
            queue_name=None if event_name != "CreateQueue" else "my-queue",
            queue_url=(
                "https://sqs.us-east-1.amazonaws.com/111122223333/my-queue"
                if event_name != "CreateQueue"
                else None
            ),
        )
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_sqs_queue_events() -> None:
    create_payload = _sqs_queue_eventbridge_envelope("CreateQueue")
    delete_payload = _sqs_queue_eventbridge_envelope(
        "DeleteQueue",
        queue_name=None,
        queue_url="https://sqs.us-east-1.amazonaws.com/111122223333/my-queue",
    )

    create_parsed = parse_cloudtrail_event(create_payload)
    delete_parsed = parse_cloudtrail_event(delete_payload)

    assert create_parsed is not None
    assert create_parsed.kind == ObjectKind.SQS_QUEUE
    assert create_parsed.action == CloudTrailEventAction.UPSERT
    assert create_parsed.identifier == "my-queue"

    assert delete_parsed is not None
    assert delete_parsed.kind == ObjectKind.SQS_QUEUE
    assert delete_parsed.action == CloudTrailEventAction.DELETE


def _ec2_instance_eventbridge_envelope(
    event_name: str,
    *,
    instance_id: str | None = "i-1234567890abcdef0",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "ec2.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account

    if event_name == "RunInstances" and instance_id is not None:
        detail["responseElements"] = {
            "instancesSet": {"items": [{"instanceId": instance_id}]}
        }
    elif instance_id is not None:
        detail["requestParameters"] = {
            "instancesSet": {"items": [{"instanceId": instance_id}]}
        }
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.ec2",
        },
    )


def test_is_supported_cloudtrail_event_true_for_ec2_instance_events() -> None:
    for event_name in ("RunInstances", "TerminateInstances"):
        payload = _ec2_instance_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_ec2_instance_events() -> None:
    create_payload = _ec2_instance_eventbridge_envelope("RunInstances")
    delete_payload = _ec2_instance_eventbridge_envelope("TerminateInstances")

    create_parsed = parse_cloudtrail_event(create_payload)
    delete_parsed = parse_cloudtrail_event(delete_payload)

    assert create_parsed is not None
    assert create_parsed.kind == ObjectKind.EC2_INSTANCE
    assert create_parsed.action == CloudTrailEventAction.UPSERT
    assert create_parsed.identifier == "i-1234567890abcdef0"

    assert delete_parsed is not None
    assert delete_parsed.kind == ObjectKind.EC2_INSTANCE
    assert delete_parsed.action == CloudTrailEventAction.DELETE


def _ec2_volume_eventbridge_envelope(
    event_name: str,
    *,
    volume_id: str | None = "vol-1234567890abcdef0",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "ec2.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account

    if event_name == "CreateVolume" and volume_id is not None:
        detail["responseElements"] = {"volumeId": volume_id}
    elif event_name == "ModifyVolume" and volume_id is not None:
        detail["requestParameters"] = {
            "ModifyVolumeRequest": {"VolumeId": volume_id, "Size": "2"}
        }
    elif volume_id is not None:
        detail["requestParameters"] = {"volumeId": volume_id}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.ec2",
        },
    )


def test_is_supported_cloudtrail_event_true_for_ec2_volume_events() -> None:
    for event_name in ("CreateVolume", "ModifyVolume", "DeleteVolume"):
        payload = _ec2_volume_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_ec2_volume_events() -> None:
    create_payload = _ec2_volume_eventbridge_envelope("CreateVolume")
    modify_payload = _ec2_volume_eventbridge_envelope("ModifyVolume")
    delete_payload = _ec2_volume_eventbridge_envelope("DeleteVolume")

    create_parsed = parse_cloudtrail_event(create_payload)
    modify_parsed = parse_cloudtrail_event(modify_payload)
    delete_parsed = parse_cloudtrail_event(delete_payload)

    assert create_parsed is not None
    assert create_parsed.kind == ObjectKind.EC2_VOLUME
    assert create_parsed.action == CloudTrailEventAction.UPSERT
    assert create_parsed.identifier == "vol-1234567890abcdef0"

    assert modify_parsed is not None
    assert modify_parsed.kind == ObjectKind.EC2_VOLUME
    assert modify_parsed.action == CloudTrailEventAction.UPSERT
    assert modify_parsed.identifier == "vol-1234567890abcdef0"

    assert delete_parsed is not None
    assert delete_parsed.kind == ObjectKind.EC2_VOLUME
    assert delete_parsed.action == CloudTrailEventAction.DELETE


def _elasticache_cluster_eventbridge_envelope(
    event_name: str,
    cache_cluster_id: str | None = "my-cache-cluster",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {
        "eventName": event_name,
        "eventSource": "elasticache.amazonaws.com",
    }
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if cache_cluster_id is not None:
        detail["requestParameters"] = {"cacheClusterId": cache_cluster_id}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {"detail": detail}
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.elasticache",
        },
    )


def test_is_supported_cloudtrail_event_true_for_elasticache_cluster_events() -> None:
    for event_name in (
        "CreateCacheCluster",
        "ModifyCacheCluster",
        "DeleteCacheCluster",
    ):
        payload = _elasticache_cluster_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_elasticache_cluster_events() -> None:
    create_payload = _elasticache_cluster_eventbridge_envelope("CreateCacheCluster")
    delete_payload = _elasticache_cluster_eventbridge_envelope("DeleteCacheCluster")

    create_parsed = parse_cloudtrail_event(create_payload)
    delete_parsed = parse_cloudtrail_event(delete_payload)

    assert create_parsed is not None
    assert create_parsed.kind == ObjectKind.ELASTICACHE_CLUSTER
    assert create_parsed.action == CloudTrailEventAction.UPSERT
    assert create_parsed.identifier == "my-cache-cluster"

    assert delete_parsed is not None
    assert delete_parsed.kind == ObjectKind.ELASTICACHE_CLUSTER
    assert delete_parsed.action == CloudTrailEventAction.DELETE
