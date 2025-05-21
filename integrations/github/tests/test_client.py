import pytest
from client import GitHubClient
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_get_paginated_handles_429(monkeypatch):
    class MockResponse:
        def __init__(self, status_code, json_data=None):
            self.status_code = status_code
            self._json = json_data or []
            self.headers = {}

        async def json(self): return self._json
        async def text(self): return str(self._json)

    async def mock_get(*args, **kwargs):
        if not hasattr(mock_get, "called"):
            mock_get.called = True
            return MockResponse(429)
        return MockResponse(200, [{"id": 1}])

    ocean = type("Ocean", (), {"create_http_client": lambda s=None: type("Client", (), {"get": mock_get})()})()
    client = GitHubClient(ocean, "dummy-token")

    result = await client._get_paginated("http://fakeurl")
    assert result == [{"id": 1}]
