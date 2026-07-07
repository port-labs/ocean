"""S3 helpers for hosting CloudFormation templates."""

from __future__ import annotations

import time

import boto3
from botocore.exceptions import ClientError

from scripts.utils.constants import DEFAULT_TEMPLATE_BUCKET_PREFIX


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
