class IncidentIoApiError(Exception):
    """incident.io returned an error or a response the integration cannot use."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class IncidentIoAuthenticationError(IncidentIoApiError):
    """The API key was rejected (HTTP 401)."""
