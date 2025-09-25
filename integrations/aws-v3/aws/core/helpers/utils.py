from typing import Any
from aiobotocore.session import AioSession
from aws.auth.region_resolver import RegionResolver


def is_access_denied_exception(e: Exception) -> bool:
    access_denied_error_codes = [
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
    ]
    response = getattr(e, "response", None)
    if isinstance(response, dict):
        error_code = response.get("Error", {}).get("Code")
        return error_code in access_denied_error_codes
    return False


def is_resource_not_found_exception(e: Exception) -> bool:
    resource_not_found_error_codes = [
        "ResourceNotFoundException",
        "ResourceNotFound",
        "ResourceNotFoundFault",
    ]
    response = getattr(e, "response", None)
    if isinstance(response, dict):
        error_code = response.get("Error", {}).get("Code")
        return error_code in resource_not_found_error_codes
    return False


def get_cluster_arn_from_service_arn(service_arn: str) -> str:
    """Extract cluster ARN from ECS service ARN.

    Args:
        service_arn: ECS service ARN in format arn:aws:ecs:region:account:service/cluster/service

    Returns:
        Cluster ARN in format arn:aws:ecs:region:account:cluster/cluster
    """
    return service_arn.replace(":service/", ":cluster/").rsplit("/", 1)[0]


async def get_allowed_regions(session: AioSession, selector: Any) -> list[str]:
    resolver = RegionResolver(session, selector)
    return list(await resolver.get_allowed_regions())
