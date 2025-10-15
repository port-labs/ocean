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


def is_recoverable_aws_exception(exception: Exception) -> bool:
    """
    Check if an AWS exception is recoverable and the action can continue.
    Recoverable exceptions (ResourceNotFound, AccessDenied) allow processing to continue.
    Non-recoverable exceptions should be re-raised to break the action.

    Args:
        exception: The exception to check

    Returns:
        True if exception is recoverable and processing can continue, False if it should be re-raised
    """
    return is_resource_not_found_exception(exception) or is_access_denied_exception(
        exception
    )


async def get_allowed_regions(session: AioSession, selector: Any) -> list[str]:
    resolver = RegionResolver(session, selector)
    return list(await resolver.get_allowed_regions())
