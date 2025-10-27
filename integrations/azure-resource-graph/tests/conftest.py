from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

import pytest
from azure.core.credentials import AccessToken
from azure.core.credentials_async import AsyncTokenCredential
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


class _DummyCredential(AsyncTokenCredential):
    async def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        return AccessToken("dummy-token", 9999999999)


class _NoOpRateLimiter:
    @asynccontextmanager
    async def limit(self, tokens: float = 1.0) -> AsyncGenerator[None, None]:
        yield


@pytest.fixture
def dummy_credential() -> _DummyCredential:
    return _DummyCredential()


@pytest.fixture
def noop_rate_limiter() -> _NoOpRateLimiter:
    return _NoOpRateLimiter()


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "azure_client_id": "123",
            "azure_client_secret": "secret",
            "azure_tenant_id": "123",
            "azure_base_url": "https://management.azure.com",
        }
        mock_ocean_app.config.resources = [
            {
                "kind": "graphResource",
                "selector": {
                    "graphQuery": "Resources | limit 1",
                },
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".id",
                            "title": ".name",
                            "blueprint": "'resource'",
                        }
                    }
                },
            }
        ]
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        # Provide an awaitable cache provider for cache_iterator_result decorator
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=None)
        mock_ocean_app.cache_provider = mock_cache

        # Use the integration class defined by this integration package
        from integration import AzureResourceGraphIntegration

        mock_ocean_app.integration = AzureResourceGraphIntegration(mock_ocean_app)

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass
