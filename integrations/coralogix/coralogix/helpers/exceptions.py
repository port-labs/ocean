class CoralogixApiError(Exception):
    """Coralogix returned an error or a response the integration cannot use."""


class CoralogixAuthenticationError(CoralogixApiError):
    """The API key was rejected (HTTP 401)."""


class CoralogixMetricsQueryError(CoralogixApiError):
    """A PromQL query failed. An empty successful result is not this error."""

    def __init__(self, query: str, detail: str) -> None:
        super().__init__(f"Coralogix metrics query failed: {detail} ({query})")
        self.query = query
        self.detail = detail
