"""EKS cluster verification helpers."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError


def verify_eks_cluster(
    session: boto3.Session,
    region: str,
    cluster_name: str,
) -> str:
    eks = session.client("eks", region_name=region)
    waiter = eks.get_waiter("cluster_active")
    try:
        waiter.wait(name=cluster_name)
    except ClientError as error:
        raise RuntimeError(
            f"EKS cluster {cluster_name} did not become active: {error}"
        ) from error
    response = eks.describe_cluster(name=cluster_name)
    return response["cluster"]["status"]
