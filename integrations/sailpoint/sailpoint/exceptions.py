class ThirdPartyAPIError(Exception):
    """Base exception for third-party API errors."""

    def __init__(self, message: str, response_code: int, response_data: Any) -> None:
        super().__init__(message)
        self.response_code = response_code
        self.response_data = response_data

def is_success(status_code: int) -> bool:
    """Check if the status code indicates a successful response."""
    return 200 <= status_code < 300
