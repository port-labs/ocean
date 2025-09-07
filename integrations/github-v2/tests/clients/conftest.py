class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 404 and self.status_code != 429:
            import httpx

            raise httpx.HTTPStatusError("error", request=None, response=None)


