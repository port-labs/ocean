from typing import Any, AsyncIterator, Protocol
import enum
import json

RAW_ITEM = dict[Any, Any]
RAW_RESULT = list[RAW_ITEM]
ASYNC_GENERATOR_RESYNC_TYPE = AsyncIterator[RAW_RESULT]


class CloudControlThrottlingConfig(enum.Enum):
    MAX_RETRY_ATTEMPTS = 100
    RETRY_MODE = "adaptive"


class CustomProperties(str, enum.Enum):
    ACCOUNT_ID = "__AccountId"
    KIND = "__Kind"
    REGION = "__Region"


class CloudControlClientProtocol(Protocol):
    async def get_resource(
        self, *, TypeName: str, Identifier: str
    ) -> dict[str, Any]: ...
    async def list_resources(
        self, *, TypeName: str, NextToken: str | None = None
    ) -> dict[str, Any]: ...


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


def is_global_resource(kind: str) -> bool:
    global_services = [
        "cloudfront",
        "route53",
        "waf",
        "waf-regional",
        "iam",
        "organizations",
        "s3",
    ]
    try:
        service = kind.split("::")[1].lower()
        return service in global_services
    except IndexError:
        return False


def fix_unserializable_date_properties(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))
