"""Classify botocore-style AWS client errors for recoverability and handling."""

_ACCESS_DENIED_ERROR_CODES = frozenset(
    {
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
    }
)
_ACCESS_DENIED_GSE_MESSAGE_PATTERNS = (
    "access denied",
    "accessdenied",
    "unauthorized",
    "forbidden",
    "permission denied",
)

_RESOURCE_NOT_FOUND_ERROR_CODES = frozenset(
    {
        "ResourceNotFoundException",
        "ResourceNotFound",
        "ResourceNotFoundFault",
        "RepositoryPolicyNotFoundException",
        "LifecyclePolicyNotFoundException",
        "RepositoryNotFoundException",
        "ClusterNotFoundException",
        "ServiceNotFoundException",
        "TaskDefinitionNotFoundException",
        "NotFoundException",
        "NoSuchBucket",
        "DBInstanceNotFound",
        "DBClusterNotFoundFault",
        "CacheClusterNotFoundFault",
        "InvalidInstanceID.NotFound",
        "InvalidVolume.NotFound",
        "AWS.SimpleQueueService.NonExistentQueue",
        "PipelineNotFoundException",
        "PipelineExecutionNotFoundException",
        "DeploymentDoesNotExistException",
        "UserNotFoundFault",
        "404",
    }
)
_RESOURCE_NOT_FOUND_GSE_MESSAGE_PATTERNS = (
    "not found",
    "notfound",
    "does not exist",
    "resourcenotfound",
)

_CLOUD_CONTROL_TYPE_UNAVAILABLE_ERROR_CODES = frozenset(
    {
        "TypeNotFoundException",
        "CFNRegistryException",
        "UnsupportedActionException",
        "ResourceNotExistsError",
    }
)
_CLOUD_CONTROL_TYPE_UNAVAILABLE_GSE_MESSAGE_PATTERNS = (
    "type not found",
    "is not registered",
    "resource type is not available in this region",
)

_THROTTLING_ERROR_CODES = frozenset(
    {
        "ThrottlingException",
        "Throttling",
    }
)


def _aws_error_code(exception: Exception) -> str | None:
    response = getattr(exception, "response", None)
    if not isinstance(response, dict):
        return None
    error = response.get("Error", {})
    if not isinstance(error, dict):
        return None
    code = error.get("Code")
    return code if isinstance(code, str) else None


def _aws_error_message_lower(exception: Exception) -> str:
    response = getattr(exception, "response", None)
    if not isinstance(response, dict):
        return ""
    error = response.get("Error", {})
    if not isinstance(error, dict):
        return ""
    message = error.get("Message", "")
    return message.lower() if isinstance(message, str) else str(message).lower()


def _matches_aws_client_error(
    exception: Exception,
    *,
    codes: frozenset[str],
    gse_message_patterns: tuple[str, ...] = (),
) -> bool:
    error_code = _aws_error_code(exception)
    if error_code is not None and error_code in codes:
        return True
    if gse_message_patterns and error_code == "GeneralServiceException":
        message = _aws_error_message_lower(exception)
        return any(pattern in message for pattern in gse_message_patterns)
    return False


def is_access_denied_exception(e: Exception) -> bool:
    return _matches_aws_client_error(
        e,
        codes=_ACCESS_DENIED_ERROR_CODES,
        gse_message_patterns=_ACCESS_DENIED_GSE_MESSAGE_PATTERNS,
    )


def is_resource_not_found_exception(e: Exception) -> bool:
    return _matches_aws_client_error(
        e,
        codes=_RESOURCE_NOT_FOUND_ERROR_CODES,
        gse_message_patterns=_RESOURCE_NOT_FOUND_GSE_MESSAGE_PATTERNS,
    )


def is_cloud_control_type_unavailable_exception(e: Exception) -> bool:
    """Return True when Cloud Control cannot handle the requested type in this region.

    Covers types that are not registered, not available, or do not support the
    requested Cloud Control action (typically ListResources / GetResource).
    """
    return _matches_aws_client_error(
        e,
        codes=_CLOUD_CONTROL_TYPE_UNAVAILABLE_ERROR_CODES,
        gse_message_patterns=_CLOUD_CONTROL_TYPE_UNAVAILABLE_GSE_MESSAGE_PATTERNS,
    )


def is_throttling_exception(e: Exception) -> bool:
    return _matches_aws_client_error(e, codes=_THROTTLING_ERROR_CODES)


def is_recoverable_aws_exception(exception: Exception) -> bool:
    """
    Check if an AWS exception is recoverable and the action can continue.
    Recoverable exceptions (ResourceNotFound, AccessDenied, Throttling) allow processing to continue.
    Non-recoverable exceptions should be re-raised to break the action.

    Args:
        exception: The exception to check

    Returns:
        True if exception is recoverable and processing can continue, False if it should be re-raised
    """
    return (
        is_resource_not_found_exception(exception)
        or is_access_denied_exception(exception)
        or is_throttling_exception(exception)
    )
