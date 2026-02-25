import pytest
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Request, Response, HTTPStatusError
from clients.aikido_client import AikidoClient
from clients.options import ListRepositoriesOptions, ListContainersOptions
from helpers.exceptions import MissingIntegrationCredentialException


@pytest.fixture
def aikido_client() -> AikidoClient:
    client = AikidoClient(
        base_url="https://api.example.com",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )
    client.auth = MagicMock()
    client.auth.get_token = AsyncMock(return_value="test_token")
    return client


@pytest.mark.asyncio
async def test_init_missing_credentials() -> None:
    with pytest.raises(MissingIntegrationCredentialException):
        AikidoClient(base_url="", client_id="", client_secret="")


@pytest.mark.asyncio
async def test_send_api_request_success(aikido_client: AikidoClient) -> None:
    test_data = {"key": "value"}
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await aikido_client._send_api_request("test_endpoint")

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_404(aikido_client: AikidoClient) -> None:
    sample_req = Request("GET", "https://api.example.com/not_found")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "404", request=sample_req, response=mock_response
    )

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await aikido_client._send_api_request("not_found")
        assert result == {}


@pytest.mark.asyncio
async def test_send_api_request_with_post_method(aikido_client: AikidoClient) -> None:
    test_data = {"result": "success"}
    json_payload = {"key": "value"}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await aikido_client._send_api_request(
            "test_endpoint", method="POST", json_data=json_payload
        )

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_with_params(aikido_client: AikidoClient) -> None:
    test_data = {"result": "success"}
    params = {"page": 1, "per_page": 50}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await aikido_client._send_api_request("test_endpoint", params=params)

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_unexpected_exception(
    aikido_client: AikidoClient,
) -> None:
    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("Unexpected error")

        with pytest.raises(Exception, match="Unexpected error"):
            await aikido_client._send_api_request("test_endpoint")


@pytest.mark.asyncio
async def test_send_api_request_non_404_http_error(aikido_client: AikidoClient) -> None:
    sample_req = Request("GET", "https://api.example.com/error")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "500 Internal Server Error", request=sample_req, response=mock_response
    )

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(HTTPStatusError):
            await aikido_client._send_api_request("test_endpoint")


@pytest.mark.asyncio
async def test_init_strips_trailing_slash_from_base_url() -> None:
    client = AikidoClient(
        base_url="https://api.example.com/",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )
    assert client.base_url == "https://api.example.com"


@pytest.mark.asyncio
async def test_get_paginated_resource_uses_first_page_and_page_size(
    aikido_client: AikidoClient,
) -> None:
    first_page = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    second_page = [{"id": "4"}]
    captured_params: list[dict[str, Any]] = []
    captured_endpoints: list[str] = []
    responses = [first_page, second_page]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:

        async def _side_effect(
            endpoint: str,
            params: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> list[dict[str, Any]]:
            captured_endpoints.append(endpoint)
            if params is not None:
                captured_params.append(params.copy())
            return responses.pop(0)

        mock_request.side_effect = _side_effect

        batches: list[list[dict[str, Any]]] = []
        async for batch in aikido_client.get_paginated_resource(
            endpoint="api/public/v1/example",
            resource_name="example",
            first_page=2,
            page_size=3,
            base_params={"include_inactive": True},
        ):
            batches.append(batch)

    assert batches == [first_page, second_page]
    assert mock_request.call_count == 2
    assert captured_endpoints == ["api/public/v1/example", "api/public/v1/example"]
    assert captured_params == [
        {"include_inactive": True, "per_page": 3, "page": 2},
        {"include_inactive": True, "per_page": 3, "page": 3},
    ]


@pytest.mark.asyncio
async def test_get_open_issue_groups_paginates(aikido_client: AikidoClient) -> None:
    first_page = [{"id": str(i)} for i in range(1, 21)]
    second_page = [{"id": "3"}]
    captured_params: list[dict[str, Any]] = []
    responses = [first_page, second_page]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:

        async def _side_effect(
            endpoint: str,
            params: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> list[dict[str, Any]]:
            if params is not None:
                captured_params.append(params.copy())
            return responses.pop(0)

        mock_request.side_effect = _side_effect

        batches: list[list[dict[str, Any]]] = []
        async for batch in aikido_client.get_open_issue_groups():
            batches.append(batch)

    assert batches == [first_page, second_page]
    assert mock_request.call_count == 2
    assert captured_params == [
        {"per_page": 20, "page": 0},
        {"per_page": 20, "page": 1},
    ]


@pytest.mark.asyncio
async def test_get_teams_paginates(aikido_client: AikidoClient) -> None:
    first_page = [{"id": str(i), "name": f"team-{i}"} for i in range(1, 21)]
    second_page = [{"id": "21", "name": "team-21"}]
    captured_params: list[dict[str, Any]] = []
    responses = [first_page, second_page]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:

        async def _side_effect(
            endpoint: str,
            params: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> list[dict[str, Any]]:
            if params is not None:
                captured_params.append(params.copy())
            return responses.pop(0)

        mock_request.side_effect = _side_effect

        batches: list[list[dict[str, Any]]] = []
        async for batch in aikido_client.get_teams():
            batches.append(batch)

    assert batches == [first_page, second_page]
    assert mock_request.call_count == 2
    assert captured_params == [
        {"per_page": 20, "page": 0},
        {"per_page": 20, "page": 1},
    ]


@pytest.mark.asyncio
async def test_get_containers_paginates(aikido_client: AikidoClient) -> None:
    first_page = [
        {"id": str(i), "name": f"container-{i}", "provider": "aws_ecr"}
        for i in range(1, 21)
    ]
    second_page = [{"id": "21", "name": "container-21", "provider": "aws_ecr"}]
    captured_params: list[dict[str, Any]] = []
    responses = [first_page, second_page]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:

        async def _side_effect(
            endpoint: str,
            params: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> list[dict[str, Any]]:
            if params is not None:
                captured_params.append(params.copy())
            return responses.pop(0)

        mock_request.side_effect = _side_effect

        batches: list[list[dict[str, Any]]] = []
        async for batch in aikido_client.get_containers():
            batches.append(batch)

    assert batches == [first_page, second_page]
    assert mock_request.call_count == 2
    assert captured_params == [
        {"per_page": 20, "page": 0},
        {"per_page": 20, "page": 1},
    ]


@pytest.mark.asyncio
async def test_get_repositories_paginates_with_default_params(
    aikido_client: AikidoClient,
) -> None:
    first_page = [{"id": str(i), "name": f"repo-{i}"} for i in range(1, 101)]
    second_page = [{"id": "21", "name": "repo-21"}]
    captured_params: list[dict[str, Any]] = []
    responses = [first_page, second_page]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:

        async def _side_effect(
            endpoint: str,
            params: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> list[dict[str, Any]]:
            if params is not None:
                captured_params.append(params.copy())
            return responses.pop(0)

        mock_request.side_effect = _side_effect

        batches: list[list[dict[str, Any]]] = []
        async for batch in aikido_client.get_repositories():
            batches.append(batch)

    assert batches == [first_page, second_page]
    assert mock_request.call_count == 2
    assert captured_params == [
        {"per_page": 100, "page": 0},
        {"per_page": 100, "page": 1},
    ]


@pytest.mark.asyncio
async def test_get_repositories_paginates_with_options(
    aikido_client: AikidoClient,
) -> None:
    first_page = [{"id": str(i), "name": f"repo-{i}"} for i in range(1, 101)]
    second_page = [{"id": "21", "name": "repo-21"}]
    captured_params: list[dict[str, Any]] = []
    responses = [first_page, second_page]

    options: ListRepositoriesOptions = {"include_inactive": True}

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:

        async def _side_effect(
            endpoint: str,
            params: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> list[dict[str, Any]]:
            if params is not None:
                captured_params.append(params.copy())
            return responses.pop(0)

        mock_request.side_effect = _side_effect

        batches: list[list[dict[str, Any]]] = []
        async for batch in aikido_client.get_repositories(options=options):
            batches.append(batch)

    assert batches == [first_page, second_page]
    assert mock_request.call_count == 2
    assert captured_params == [
        {"include_inactive": True, "per_page": 100, "page": 0},
        {"include_inactive": True, "per_page": 100, "page": 1},
    ]


@pytest.mark.asyncio
async def test_get_containers_paginates_with_options(
    aikido_client: AikidoClient,
) -> None:
    first_page = [{"id": str(i), "name": f"container-{i}"} for i in range(1, 21)]
    second_page = [{"id": "21", "name": "container-21"}]
    captured_params: list[dict[str, Any]] = []
    responses = [first_page, second_page]

    options: ListContainersOptions = {"filter_status": "inactive"}

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:

        async def _side_effect(
            endpoint: str,
            params: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> list[dict[str, Any]]:
            if params is not None:
                captured_params.append(params.copy())
            return responses.pop(0)

        mock_request.side_effect = _side_effect

        batches: list[list[dict[str, Any]]] = []
        async for batch in aikido_client.get_containers(options=options):
            batches.append(batch)

    assert batches == [first_page, second_page]
    assert mock_request.call_count == 2
    assert captured_params == [
        {"filter_status": "inactive", "per_page": 20, "page": 0},
        {"filter_status": "inactive", "per_page": 20, "page": 1},
    ]
