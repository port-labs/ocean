import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from harbor.clients.http.harbor_client import HarborClient
from harbor.helpers.utils import IgnoredError
from harbor.helpers.exceptions import InvalidTokenException


@pytest.mark.asyncio
class TestHarborClient:
    async def test_client_creation(self) -> None:
        """Test that HarborClient can be created with authenticator."""
        mock_authenticator = MagicMock()
        mock_authenticator.client = MagicMock()

        client1 = HarborClient("http://localhost:8081", mock_authenticator)
        client2 = HarborClient("http://localhost:8081", mock_authenticator)

        assert client1 is not client2

    async def test_client_initialization(self, harbor_client: HarborClient) -> None:
        """Test HarborClient initialization."""
        assert harbor_client.base_url == "http://localhost:8081"
        assert harbor_client.api_url == "http://localhost:8081/api/v2.0"
        assert harbor_client._authenticator is not None

    async def test_make_request_success(self, harbor_client: HarborClient) -> None:
        """Test successful API request."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.headers = {"content-type": "application/json"}

        mock_headers = MagicMock()
        mock_headers.as_dict.return_value = {
            "Authorization": "Basic test",
            "Accept": "application/json",
        }

        with patch.object(
            harbor_client._authenticator,
            "get_headers",
            AsyncMock(return_value=mock_headers),
        ):
            with patch.object(
                harbor_client.client, "request", AsyncMock(return_value=mock_response)
            ):
                result = await harbor_client.make_request("/test")

                assert result == mock_response

    async def test_make_request_http_error(self, harbor_client: HarborClient) -> None:
        """Test API request with HTTP error."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_http_error = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        mock_headers = MagicMock()
        mock_headers.as_dict.return_value = {
            "Authorization": "Basic test",
            "Accept": "application/json",
        }

        with patch.object(
            harbor_client._authenticator,
            "get_headers",
            AsyncMock(return_value=mock_headers),
        ):
            with patch.object(
                harbor_client.client, "request", AsyncMock(side_effect=mock_http_error)
            ):
                with pytest.raises(InvalidTokenException):
                    await harbor_client.make_request("/test")

    async def test_make_request_with_ignored_error(
        self, harbor_client: HarborClient
    ) -> None:
        """Test API request with ignored error."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        mock_http_error = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        mock_headers = MagicMock()
        mock_headers.as_dict.return_value = {
            "Authorization": "Basic test",
            "Accept": "application/json",
        }

        ignored_errors = [IgnoredError(status=404, message="Resource not found")]

        with patch.object(
            harbor_client._authenticator,
            "get_headers",
            AsyncMock(return_value=mock_headers),
        ):
            with patch.object(
                harbor_client.client, "request", AsyncMock(side_effect=mock_http_error)
            ):
                result = await harbor_client.make_request(
                    "/test", ignored_errors=ignored_errors
                )

                assert result.status_code == 200
                assert result.content == b"{}"

    async def test_send_paginated_request_single_page(
        self, harbor_client: HarborClient
    ) -> None:
        """Test paginated request with single page."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "project1"}]
        mock_response.headers = {}

        with patch.object(
            harbor_client, "make_request", AsyncMock(return_value=mock_response)
        ) as mock_make_request:
            results = []
            async for page in harbor_client.send_paginated_request(
                "/projects", params={"page_size": 2}
            ):
                results.append(page)

            assert mock_make_request.call_count == 1
            assert len(results) == 1
            assert len(results[0]) == 1
            assert results[0][0]["name"] == "project1"

    async def test_send_paginated_request_multiple_pages(
        self, harbor_client: HarborClient
    ) -> None:
        """Test paginated request with multiple pages."""
        mock_response1 = MagicMock(spec=httpx.Response)
        mock_response1.status_code = 200
        mock_response1.json.return_value = [
            {"id": 1, "name": "project1"},
            {"id": 2, "name": "project2"},
        ]
        mock_response1.headers = {
            "Link": '</api/v2.0/projects?page=2&page_size=2>; rel="next"'
        }

        mock_response2 = MagicMock(spec=httpx.Response)
        mock_response2.status_code = 200
        mock_response2.json.return_value = [{"id": 3, "name": "project3"}]
        mock_response2.headers = {}

        mock_headers = MagicMock()
        mock_headers.as_dict.return_value = {
            "Authorization": "Basic test",
            "Accept": "application/json",
        }
        with patch.object(
            harbor_client._authenticator,
            "get_headers",
            AsyncMock(return_value=mock_headers),
        ):
            with patch.object(
                harbor_client,
                "make_request",
                AsyncMock(side_effect=[mock_response1, mock_response2]),
            ):
                results = []
                async for page in harbor_client.send_paginated_request(
                    "/projects", params={"page_size": 2}
                ):
                    results.append(page)

                assert len(results) == 2
                assert len(results[0]) == 2
                assert len(results[1]) == 1

    async def test_send_paginated_request_404_stops_pagination(
        self, harbor_client: HarborClient
    ) -> None:
        """Test that 404 error stops pagination."""
        mock_response1 = MagicMock(spec=httpx.Response)
        mock_response1.status_code = 200
        mock_response1.json.return_value = [
            {"id": 1, "name": "project1"},
            {"id": 2, "name": "project2"},
        ]
        mock_response1.headers = {
            "Link": '</api/v2.0/projects?page=2&page_size=2>; rel="next"'
        }

        mock_response2 = MagicMock(spec=httpx.Response)
        mock_response2.status_code = 404
        mock_response2.text = "Not Found"
        mock_response2.headers = {}

        mock_http_error = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response2
        )

        mock_headers = MagicMock()
        mock_headers.as_dict.return_value = {
            "Authorization": "Basic test",
            "Accept": "application/json",
        }
        with patch.object(
            harbor_client._authenticator,
            "get_headers",
            AsyncMock(return_value=mock_headers),
        ):
            with patch.object(
                harbor_client,
                "make_request",
                AsyncMock(side_effect=[mock_response1, mock_http_error]),
            ):
                results = []
                with pytest.raises(httpx.HTTPStatusError):
                    async for page in harbor_client.send_paginated_request(
                        "/projects", params={"page_size": 2}
                    ):
                        results.append(page)

                assert len(results) == 1
                assert len(results[0]) == 2
                assert results[0][0]["name"] == "project1"
                assert results[0][1]["name"] == "project2"

    async def test_base_url_property(self, harbor_client: HarborClient) -> None:
        """Test base_url property."""
        expected_url = "http://localhost:8081"
        assert harbor_client.base_url == expected_url

    async def test_make_request_with_params(self, harbor_client: HarborClient) -> None:
        """Test make_request with query parameters."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}

        # Mock the authenticator's get_headers method
        mock_headers = MagicMock()
        mock_headers.as_dict.return_value = {
            "Authorization": "Basic test",
            "Accept": "application/json",
        }
        with patch.object(
            harbor_client._authenticator,
            "get_headers",
            AsyncMock(return_value=mock_headers),
        ):
            with patch.object(
                harbor_client.client, "request", AsyncMock(return_value=mock_response)
            ) as mock_request:
                await harbor_client.make_request(
                    "/projects",
                    params={"page": 1, "page_size": 10, "name": "test"},
                    method="GET",
                )

                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert call_args[1]["params"]["page"] == 1
                assert call_args[1]["params"]["page_size"] == 10
                assert call_args[1]["params"]["name"] == "test"
                assert call_args[1]["method"] == "GET"

    async def test_make_request_with_json_data(
        self, harbor_client: HarborClient
    ) -> None:
        """Test make_request with JSON data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "created"}

        mock_headers = MagicMock()
        mock_headers.as_dict.return_value = {
            "Authorization": "Basic test",
            "Accept": "application/json",
        }
        with patch.object(
            harbor_client._authenticator,
            "get_headers",
            AsyncMock(return_value=mock_headers),
        ):
            json_data = {"name": "new-project", "public": True}

            with patch.object(
                harbor_client.client, "request", AsyncMock(return_value=mock_response)
            ) as mock_request:
                await harbor_client.make_request(
                    "/projects", method="POST", json_data=json_data
                )

                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert call_args[1]["json"] == json_data
                assert call_args[1]["method"] == "POST"
