from typing import Any, Optional


class ThirdPartyAPIError(Exception):
    """Base exception for third-party API errors."""
    def __init__(
        self,
        message: str,
        response_code: Optional[int] = None,
        response_data: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.response_code = response_code
        self.response_data = response_data


def is_success(status_code: int) -> bool:
    """Check if the status code indicates a successful response."""
    return 200 <= status_code < 300


class SailPointAuthError(ThirdPartyAPIError):
    """Raised for authentication errors with SailPoint API"""

    def __init__(
        self,
        message: str = "Authentication error with SailPoint API",
        response_code: Optional[int] = None,
        response_data: Optional[Any] = None,
    ) -> None:
        super().__init__(message, response_code, response_data)


class SailPointTokenExpiredError(SailPointAuthError):
    """Raised when the SailPoint API token has expired"""

    def __init__(
        self,
        response_code: Optional[int] = None,
        response_data: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message="SailPoint API token has expired",
            response_code=response_code,
            response_data=response_data,
        )
