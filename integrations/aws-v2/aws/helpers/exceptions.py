class CredentialsProviderError(Exception): ...


def is_access_denied_exception(e: Exception) -> bool:
    access_denied_error_codes = [
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
    ]

    if hasattr(e, "response") and e.response is not None:
        error_code = e.response.get("Error", {}).get("Code")
        return error_code in access_denied_error_codes

    return False


def is_server_error(e: Exception) -> bool:
    if hasattr(e, "response"):
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return status >= 500

    return False


def is_resource_not_found_exception(e: Exception) -> bool:
    resource_not_found_error_codes = [
        "ResourceNotFoundException",
        "ResourceNotFound",
        "ResourceNotFoundFault",
    ]

    if hasattr(e, "response") and e.response is not None:
        error_code = e.response.get("Error", {}).get("Code")
        return error_code in resource_not_found_error_codes

    return False
