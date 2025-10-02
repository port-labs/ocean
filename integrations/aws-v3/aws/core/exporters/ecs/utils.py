"""ECS-specific utility functions."""


def get_cluster_arn_from_service_arn(service_arn: str) -> str:
    """Extract cluster ARN from ECS service ARN.

    Args:
        service_arn: ECS service ARN in format arn:aws:ecs:region:account:service/cluster/service

    Returns:
        Cluster ARN in format arn:aws:ecs:region:account:cluster/cluster
    """
    return service_arn.replace(":service/", ":cluster/").rsplit("/", 1)[0]
