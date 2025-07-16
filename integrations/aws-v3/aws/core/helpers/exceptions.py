from typing import Optional
from botocore.exceptions import ClientError


class AWSClientError(ClientError):
    """Raised when there is an error creating an AWS client."""

    @staticmethod
    def is_access_denied_exception(e: Optional[Exception]) -> bool:
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

    @staticmethod
    def is_resource_not_found_exception(e: Optional[Exception]) -> bool:
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
