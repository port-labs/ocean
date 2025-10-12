from unittest.mock import patch, Mock, AsyncMock
import asyncio
import pytest
from httpx import Response, Request, HTTPStatusError

from harbor.client import HarborClient
from harbor.constants import DEFAULT_TIMEOUT, DEFAULT_MAX_CONCURRENT_REQUESTS
from harbor.exceptions import HarborAPIError, ServerError, UnauthorizedError, ForbiddenError, NotFoundError, InvalidConfigurationError, MissingCredentialsError, RateLimitError
from tests.fixtures import harbor_config, harbor_client, mock_async_client, mock_project_response, mock_user_response, mock_repository_response, mock_artifact_response

class TestHarborClientSetup:

    def test_client_initialization(self, harbor_config):
        client = HarborClient(**harbor_config, verify_ssl=False)
        assert client.base_url == harbor_config['base_url']
        assert client.username == harbor_config['username']
        assert client.password == harbor_config['password']
        assert client.verify_ssl is False

        assert client.client is not None
        assert client._semaphore is not None

    def test_init_strips_trailing_slash_base_url(self, harbor_config):
        harbor_config['base_url'] = 'https://harbor.onmypc.com/'
        client = HarborClient(
            **harbor_config,
            verify_ssl=False
        )
        assert client.base_url == 'https://harbor.onmypc.com'

    def test_init_raises_invalid_configuration_error(self):
        with pytest.raises(InvalidConfigurationError):
            HarborClient(base_url='', username='user', password='pass')

        with pytest.raises(MissingCredentialsError):
            HarborClient(base_url='https://harbor.onmypc.com', username='', password='pass')

        with pytest.raises(MissingCredentialsError):
            HarborClient(base_url='https://harbor.onmypc.com', username='user', password='')

        with pytest.raises(MissingCredentialsError):
            HarborClient(base_url='https://harbor.onmypc.com', username=None, password='pass')
