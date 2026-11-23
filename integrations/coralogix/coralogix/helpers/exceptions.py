class CoralogixApiError(Exception):
    """Coralogix returned an error or a response the integration cannot use."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CoralogixAuthenticationError(CoralogixApiError):
    """The API key was rejected (HTTP 401)."""


class CoralogixMetricsQueryError(CoralogixApiError):
    """A PromQL query failed. An empty successful result is not this error."""

    def __init__(self, query: str, detail: str) -> None:
        super().__init__(f"Coralogix metrics query failed: {detail} ({query})")
        self.query = query
        self.detail = detail
