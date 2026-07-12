"""S3 helpers for hosting CloudFormation templates."""

from __future__ import annotations

import json
import time

import boto3
from botocore.exceptions import ClientError

from scripts.utils.constants import DEFAULT_TEMPLATE_BUCKET_PREFIX
from scripts.utils.logging import logger


def get_account_id(session: boto3.Session) -> str:
    return session.client("sts").get_caller_identity()["Account"]


def get_partition(session: boto3.Session) -> str:
    arn = session.client("sts").get_caller_identity()["Arn"]
    return arn.split(":")[1]


def resolve_organization_id(
    management_session: boto3.Session,
    organization_id: str | None,
) -> str:
    if organization_id:
        return organization_id
    try:
        organizations = management_session.client("organizations")
        return organizations.describe_organization()["Organization"]["Id"]
    except ClientError as error:
        raise ValueError(
            "Set ORGANIZATION_ID in the configuration section, or grant "
            "organizations:DescribeOrganization on the management account."
        ) from error


def ensure_template_bucket(
    session: boto3.Session,
    region: str,
    bucket_name: str | None,
) -> str:
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    bucket = bucket_name or f"{DEFAULT_TEMPLATE_BUCKET_PREFIX}-{account_id}-{region}"
    s3 = session.client("s3", region_name=region)

    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code not in {"404", "NoSuchBucket", "403"}:
            raise
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        for _ in range(10):
            try:
                s3.head_bucket(Bucket=bucket)
                break
            except ClientError:
                time.sleep(1)
        else:
            raise TimeoutError(f"Timed out waiting for bucket {bucket}")

    s3.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    return bucket


def upload_template(
    session: boto3.Session,
    *,
    region: str,
    bucket: str,
    key: str,
    template_body: str,
) -> str:
    s3 = session.client("s3", region_name=region)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=template_body.encode("utf-8"),
        ContentType="text/yaml",
    )
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def build_template_bucket_policy(
    *,
    bucket: str,
    partition: str,
    management_account_id: str,
    organization_id: str,
) -> dict:
    bucket_arn = f"arn:{partition}:s3:::{bucket}"
    object_arn = f"{bucket_arn}/*"
    management_root = f"arn:{partition}:iam::{management_account_id}:root"
    read_actions = [
        "s3:GetBucketLocation",
        "s3:GetObject",
        "s3:GetObjectVersion",
    ]
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowManagementAccountRead",
                "Effect": "Allow",
                "Principal": {"AWS": management_root},
                "Action": read_actions,
                "Resource": [bucket_arn, object_arn],
            },
            {
                "Sid": "AllowCloudFormationManagementAccount",
                "Effect": "Allow",
                "Principal": {"Service": "cloudformation.amazonaws.com"},
                "Action": read_actions,
                "Resource": [bucket_arn, object_arn],
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": management_account_id},
                },
            },
            {
                "Sid": "AllowCloudFormationMemberAccounts",
                "Effect": "Allow",
                "Principal": {"Service": "cloudformation.amazonaws.com"},
                "Action": read_actions,
                "Resource": [bucket_arn, object_arn],
                "Condition": {
                    "StringEquals": {"aws:PrincipalOrgID": organization_id},
                },
            },
        ],
    }


def apply_template_bucket_cross_account_policy(
    integration_session: boto3.Session,
    *,
    region: str,
    bucket: str,
    management_account_id: str,
    organization_id: str,
) -> None:
    partition = get_partition(integration_session)
    policy = build_template_bucket_policy(
        bucket=bucket,
        partition=partition,
        management_account_id=management_account_id,
        organization_id=organization_id,
    )
    s3 = integration_session.client("s3", region_name=region)
    s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
    logger.info(
        "Applied cross-account template bucket policy for management account "
        f"{management_account_id} and organization {organization_id}."
    )


def ensure_integration_template_bucket(
    integration_session: boto3.Session,
    management_session: boto3.Session,
    region: str,
    bucket_name: str | None,
    *,
    organization_id: str | None = None,
) -> str:
    bucket = ensure_template_bucket(integration_session, region, bucket_name)
    management_account_id = get_account_id(management_session)
    resolved_organization_id = resolve_organization_id(
        management_session,
        organization_id,
    )
    apply_template_bucket_cross_account_policy(
        integration_session,
        region=region,
        bucket=bucket,
        management_account_id=management_account_id,
        organization_id=resolved_organization_id,
    )
    logger.info(f"Using integration-account template bucket: {bucket}")
    return bucket
