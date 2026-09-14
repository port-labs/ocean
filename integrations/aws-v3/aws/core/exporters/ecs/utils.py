"""ECS-specific utility functions."""

from aws.utils import RegionHelper


def _service_arn_resource(service_arn: str) -> str:
    return service_arn.split(":service/", 1)[-1]


def is_short_service_arn(service_arn: str) -> bool:
    """Return True when the ARN uses the legacy ``:service/{service-name}`` format."""
    return "/" not in _service_arn_resource(service_arn)


def normalize_service_arn(
    service_arn: str, cluster_arn: str | None = None
) -> str | None:
    """Normalize a service ARN to the long ``:service/{cluster}/{service}`` format."""
    resource = _service_arn_resource(service_arn)
    if "/" in resource:
        return service_arn
    if not cluster_arn:
        return None

    cluster_name = cluster_arn.rsplit("/", 1)[-1]
    prefix = service_arn.rsplit(":service/", 1)[0]
    return f"{prefix}:service/{cluster_name}/{resource}"


def _cluster_name_from_identifier(cluster: str) -> str:
    if ":cluster/" in cluster:
        return cluster.rsplit("/", 1)[-1]
    return cluster


def _service_name_from_identifier(service: str) -> str:
    if ":service/" not in service:
        return service

    resource = _service_arn_resource(service)
    if "/" in resource:
        return resource.split("/", 1)[1]
    return resource


def parse_service_arn(service_arn: str) -> tuple[str, str]:
    """Extract cluster name and service name from a long-form ECS service ARN."""
    resource = _service_arn_resource(service_arn)
    cluster_name, service_name = resource.split("/", 1)
    if ":cluster/" in cluster_name:
        cluster_name = cluster_name.rsplit("/", 1)[-1]
    return cluster_name, service_name


def build_service_arn(region: str, account_id: str, cluster: str, service: str) -> str:
    """Build an ECS service ARN from cluster and service identifiers."""
    if ":service/" in service and not is_short_service_arn(service):
        return service

    partition = RegionHelper.get_partition()
    cluster_name = _cluster_name_from_identifier(cluster)

    if ":service/" in service:
        cluster_arn = (
            cluster
            if ":cluster/" in cluster
            else (f"arn:{partition}:ecs:{region}:{account_id}:cluster/{cluster_name}")
        )
        normalized = normalize_service_arn(service, cluster_arn)
        if normalized:
            return normalized

    service_name = _service_name_from_identifier(service)
    return (
        f"arn:{partition}:ecs:{region}:{account_id}:service/"
        f"{cluster_name}/{service_name}"
    )


def get_cluster_arn_from_service_arn(service_arn: str) -> str:
    """Extract cluster ARN from ECS service ARN.

    Args:
        service_arn: ECS service ARN in format arn:partition:ecs:region:account:service/cluster/service

    Returns:
        Cluster ARN in format arn:partition:ecs:region:account:cluster/cluster
    """
    return service_arn.replace(":service/", ":cluster/").rsplit("/", 1)[0]
