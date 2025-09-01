import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Request, Response, HTTPStatusError
from clients.armorcode_client import ArmorcodeClient


@pytest.fixture
def armorcode_client() -> ArmorcodeClient:
    client = ArmorcodeClient(
        base_url="https://app.armorcode.com",
        api_key="test_api_key",
    )
    return client


@pytest.mark.asyncio
async def test_init_strips_trailing_slash_from_base_url() -> None:
    client = ArmorcodeClient(
        base_url="https://app.armorcode.com/",
        api_key="test_api_key",
    )
    assert client.base_url == "https://app.armorcode.com"


@pytest.mark.asyncio
async def test_send_api_request_success(armorcode_client: ArmorcodeClient) -> None:
    test_data = {"key": "value"}
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {"X-Rate-Limit-Remaining": "299"}

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await armorcode_client._send_api_request("test_endpoint")

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_404(armorcode_client: ArmorcodeClient) -> None:
    sample_req = Request("GET", "https://app.armorcode.com/not_found")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "404", request=sample_req, response=mock_response
    )

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await armorcode_client._send_api_request("not_found")
        assert result == {}


@pytest.mark.asyncio
async def test_send_api_request_with_post_method(
    armorcode_client: ArmorcodeClient,
) -> None:
    test_data = {"result": "success"}
    json_payload = {"key": "value"}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {"X-Rate-Limit-Remaining": "299"}

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await armorcode_client._send_api_request(
            "test_endpoint", method="POST", json_data=json_payload
        )

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_with_params(armorcode_client: ArmorcodeClient) -> None:
    test_data = {"result": "success"}
    params = {"page": 1, "per_page": 50}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {"X-Rate-Limit-Remaining": "299"}

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await armorcode_client._send_api_request(
            "test_endpoint", params=params
        )

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_unexpected_exception(
    armorcode_client: ArmorcodeClient,
) -> None:
    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("Unexpected error")

        with pytest.raises(Exception, match="Unexpected error"):
            await armorcode_client._send_api_request("test_endpoint")


@pytest.mark.asyncio
async def test_send_api_request_non_404_http_error(
    armorcode_client: ArmorcodeClient,
) -> None:
    sample_req = Request("GET", "https://app.armorcode.com/error")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "500 Internal Server Error", request=sample_req, response=mock_response
    )

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(HTTPStatusError):
            await armorcode_client._send_api_request("test_endpoint")


@pytest.mark.asyncio
async def test_get_products_success(armorcode_client: ArmorcodeClient) -> None:
    mock_response = {
        "content": [{"id": "1", "name": "Product 1"}, {"id": "2", "name": "Product 2"}],
        "last": True,
    }

    with patch.object(
        armorcode_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        products = []
        async for batch in armorcode_client.get_products():
            products.extend(batch)

        assert len(products) == 2
        assert products[0]["id"] == "1"
        assert products[1]["id"] == "2"


@pytest.mark.asyncio
async def test_get_all_subproducts_success(armorcode_client: ArmorcodeClient) -> None:
    mock_response = {
        "content": [
            {"id": "1", "name": "SubProduct 1"},
            {"id": "2", "name": "SubProduct 2"},
        ]
    }

    with patch.object(
        armorcode_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        subproducts = []
        async for batch in armorcode_client.get_all_subproducts():
            subproducts.extend(batch)

        assert len(subproducts) == 2
        assert subproducts[0]["id"] == "1"
        assert subproducts[1]["id"] == "2"


@pytest.mark.asyncio
async def test_get_all_findings_success(armorcode_client: ArmorcodeClient) -> None:
    mock_response = {
        "data": {
            "findings": [
                {"id": "1", "title": "Finding 1"},
                {"id": "2", "title": "Finding 2"},
            ],
            "afterKey": None,  # Set to None to break the loop
        }
    }

    with patch.object(
        armorcode_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        findings = []
        async for batch in armorcode_client.get_all_findings():
            findings.extend(batch)

        assert len(findings) == 2
        assert findings[0]["id"] == "1"
        assert findings[1]["id"] == "2"


@pytest.mark.asyncio
async def test_get_all_findings_pagination(armorcode_client: ArmorcodeClient) -> None:
    # First response with afterKey
    first_response = {
        "data": {
            "findings": [{"id": "1", "title": "Finding 1"}],
            "afterKey": "next_key",
        }
    }

    # Second response without afterKey (last page)
    second_response = {
        "data": {"findings": [{"id": "2", "title": "Finding 2"}], "afterKey": None}
    }

    with patch.object(
        armorcode_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_response, second_response]

        findings = []
        async for batch in armorcode_client.get_all_findings():
            findings.extend(batch)

        assert len(findings) == 2
        assert findings[0]["id"] == "1"
        assert findings[1]["id"] == "2"
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_get_products_empty_response(armorcode_client: ArmorcodeClient) -> None:
    mock_response = {"content": [], "last": True}

    with patch.object(
        armorcode_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        products = []
        async for batch in armorcode_client.get_products():
            products.extend(batch)

        assert len(products) == 0


@pytest.mark.asyncio
async def test_get_all_findings_empty_response(
    armorcode_client: ArmorcodeClient,
) -> None:
    mock_response: dict[str, dict[str, list[dict[str, object]]]] = {
        "data": {"findings": []}
    }

    with patch.object(
        armorcode_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        findings = []
        async for batch in armorcode_client.get_all_findings():
            findings.extend(batch)

        assert len(findings) == 0
