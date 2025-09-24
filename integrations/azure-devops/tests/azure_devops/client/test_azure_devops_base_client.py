import pytest
from unittest.mock import AsyncMock, patch
from httpx import Response, ReadTimeout
from azure_devops.client.base_client import HTTPBaseClient, CONTINUATION_TOKEN_HEADER


@pytest.fixture
def mock_client() -> HTTPBaseClient:
    return HTTPBaseClient(personal_access_token="test_token")


@pytest.mark.asyncio
async def test_get_paginated_by_top_and_continuation_token_single_page(
    mock_client: HTTPBaseClient,
) -> None:
    """Test pagination with a single page of results (no continuation token)."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.json.return_value = {"value": [{"id": 1}, {"id": 2}]}

    with patch.object(
        mock_client, "send_request", return_value=mock_response
    ) as mock_send:
        generator = mock_client._get_paginated_by_top_and_continuation_token("test_url")
        results = [item async for page in generator for item in page]

        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[1]["id"] == 2
        mock_send.assert_called_once_with("GET", "test_url", params={"$top": 50})


@pytest.mark.asyncio
async def test_get_paginated_by_top_and_continuation_token_multiple_pages(
    mock_client: HTTPBaseClient,
) -> None:
    """Test pagination with multiple pages using continuation token."""
    mock_response1 = AsyncMock(spec=Response)
    mock_response1.status_code = 200
    mock_response1.headers = {CONTINUATION_TOKEN_HEADER: "token123"}
    mock_response1.json.return_value = {"value": [{"id": 1}, {"id": 2}]}

    mock_response2 = AsyncMock(spec=Response)
    mock_response2.status_code = 200
    mock_response2.headers = {}
    mock_response2.json.return_value = {"value": [{"id": 3}, {"id": 4}]}

    with patch.object(
        mock_client, "send_request", side_effect=[mock_response1, mock_response2]
    ) as mock_send:
        generator = mock_client._get_paginated_by_top_and_continuation_token("test_url")
        results = [item async for page in generator for item in page]

        assert len(results) == 4
        assert results[0]["id"] == 1
        assert results[3]["id"] == 4

        assert mock_send.call_count == 2
        mock_send.assert_any_call("GET", "test_url", params={"$top": 50})
        mock_send.assert_any_call(
            "GET", "test_url", params={"$top": 50, "continuationToken": "token123"}
        )


@pytest.mark.asyncio
async def test_get_paginated_by_top_and_continuation_token_with_custom_data_key(
    mock_client: HTTPBaseClient,
) -> None:
    """Test pagination with a custom data key (not 'value')."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.json.return_value = {"items": [{"id": 1}]}

    with patch.object(mock_client, "send_request", return_value=mock_response):
        generator = mock_client._get_paginated_by_top_and_continuation_token(
            "test_url", data_key="items"
        )
        results = [item async for page in generator for item in page]

        assert len(results) == 1
        assert results[0]["id"] == 1


@pytest.mark.asyncio
async def test_get_paginated_by_top_and_continuation_token_retry_on_timeout(
    mock_client: HTTPBaseClient,
) -> None:
    """Test pagination retries successfully after a timeout."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.json.return_value = {"value": [{"id": 1}]}

    with patch.object(
        mock_client,
        "send_request",
        side_effect=[ReadTimeout("Request timed out"), mock_response],
    ) as mock_send:
        generator = mock_client._get_paginated_by_top_and_continuation_token("test_url")
        results = [item async for page in generator for item in page]

        assert len(results) == 1
        assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_get_paginated_by_top_and_continuation_token_exhausts_retries(
    mock_client: HTTPBaseClient,
) -> None:
    """Test pagination raises ReadTimeout after exhausting retries."""
    side_effects = [
        ReadTimeout("Request timed out 1"),
        ReadTimeout("Request timed out 2"),
        ReadTimeout("Request timed out 3"),
    ]
    with patch.object(
        mock_client, "send_request", side_effect=side_effects
    ) as mock_send:
        with pytest.raises(ReadTimeout):
            generator = mock_client._get_paginated_by_top_and_continuation_token(
                "test_url"
            )
            _ = [item async for page in generator for item in page]

        assert mock_send.call_count == 3


@pytest.mark.asyncio
async def test_get_paginated_by_top_and_skip_retry_on_timeout(
    mock_client: HTTPBaseClient,
) -> None:
    """Test _get_paginated_by_top_and_skip retries successfully after a timeout."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": [{"id": 1}]}

    with patch.object(
        mock_client,
        "send_request",
        side_effect=[ReadTimeout("Request timed out"), mock_response],
    ) as mock_send:
        generator = mock_client._get_paginated_by_top_and_skip("test_url")
        results = [item async for page in generator for item in page]

        assert len(results) == 1
        assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_get_paginated_by_top_and_skip_exhausts_retries(
    mock_client: HTTPBaseClient,
) -> None:
    """Test _get_paginated_by_top_and_skip raises ReadTimeout after exhausting retries."""
    side_effects = [
        ReadTimeout("Request timed out 1"),
        ReadTimeout("Request timed out 2"),
        ReadTimeout("Request timed out 3"),
    ]
    with patch.object(
        mock_client, "send_request", side_effect=side_effects
    ) as mock_send:
        with pytest.raises(ReadTimeout):
            generator = mock_client._get_paginated_by_top_and_skip("test_url")
            _ = [item async for page in generator for item in page]

        assert mock_send.call_count == 3
