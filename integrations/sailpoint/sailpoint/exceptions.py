from typing import Any


class ThirdPartyAPIError(Exception):
    """Base exception for third-party API errors."""

    def __init__(self, message: str, response_code: int, response_data: Any) -> None:
        super().__init__(message)
        self.response_code = response_code
        self.response_data = response_data


def is_success(status_code: int) -> bool:
    """Check if the status code indicates a successful response."""
    return 200 <= status_code < 300


class SailPointAuthError(ThirdPartyAPIError):
    """Raised for authentication errors with SailPoint API"""

    def __init__(self, response_code: int, response_data: Any) -> None:
        super().__init__(
            "Authentication error with SailPoint API", response_code, response_data
        )


class SailPointTokenExpiredError(SailPointAuthError):
    """Raised when the SailPoint API token has expired"""

    def __init__(self, response_code: int, response_data: Any) -> None:
        super().__init__(response_code, response_data)
        self.message = "SailPoint API token has expired"
