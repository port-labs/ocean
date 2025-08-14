from typing import Any
from aiobotocore.session import AioSession
from aws.auth.region_resolver import RegionResolver
from botocore.utils import ArnParser


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


async def get_allowed_regions(session: AioSession, selector: Any) -> list[str]:
    resolver = RegionResolver(session, selector)
    return list(await resolver.get_allowed_regions())


def extract_resource_name_from_arn(
    arn: str, arn_parser: ArnParser = ArnParser()
) -> str:
    """Extract resource name from ARN. Raises if parsing fails."""
    arn_data = arn_parser.parse_arn(arn)
    resource = arn_data["resource"]
    return resource.split("/")[-1] if "/" in resource else resource
