"""ECS-specific utility functions."""

from aws.utils import RegionHelper


def parse_service_arn(service_arn: str) -> tuple[str, str]:
    """Extract cluster name and service name from an ECS service ARN."""
    resource = service_arn.split(":service/", 1)[-1]
    cluster_name, service_name = resource.split("/", 1)
    if ":cluster/" in cluster_name:
        cluster_name = cluster_name.rsplit("/", 1)[-1]
    return cluster_name, service_name


def build_service_arn(region: str, account_id: str, cluster: str, service: str) -> str:
    """Build an ECS service ARN from cluster and service identifiers."""
    partition = RegionHelper.get_partition()
    cluster_name = cluster.rsplit("/", 1)[-1] if ":cluster/" in cluster else cluster
    return (
        f"arn:{partition}:ecs:{region}:{account_id}:service/"
        f"{cluster_name}/{service}"
    )


def get_cluster_arn_from_service_arn(service_arn: str) -> str:
    """Extract cluster ARN from ECS service ARN.

    Args:
        service_arn: ECS service ARN in format arn:partition:ecs:region:account:service/cluster/service

    Returns:
        Cluster ARN in format arn:partition:ecs:region:account:cluster/cluster
    """
    return service_arn.replace(":service/", ":cluster/").rsplit("/", 1)[0]
