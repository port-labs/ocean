import pytest
from typing import Any, Optional
from unittest.mock import AsyncMock, call, patch, MagicMock

from client import KomodorClient, SERVICES_PAGE_SIZE
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

API_URL = "https://api.komodor.com/api/v2"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "api_key": "test_api_key",
            "api_url": API_URL,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_komodor_client() -> KomodorClient:
    return KomodorClient(api_key="test_api_key", api_url=API_URL)


@pytest.mark.asyncio
async def test_get_all_services_omits_cursor_on_first_request(
    mock_komodor_client: KomodorClient,
) -> None:
    with patch.object(
        mock_komodor_client, "_send_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [service_page("1")]

        await collect_services(mock_komodor_client)

        assert mock_request.call_args == search_call({"pageSize": SERVICES_PAGE_SIZE})


@pytest.mark.asyncio
async def test_get_all_services_follows_token_across_pages(
    mock_komodor_client: KomodorClient,
) -> None:
    with patch.object(
        mock_komodor_client, "_send_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            service_page("1", next_token="cursor-1"),
            service_page("2", next_token="cursor-2"),
            service_page("3"),
        ]

        await collect_services(mock_komodor_client)

        assert mock_request.call_args_list == [
            search_call({"pageSize": SERVICES_PAGE_SIZE}),
            search_call({"pageSize": SERVICES_PAGE_SIZE, "token": "cursor-1"}),
            search_call({"pageSize": SERVICES_PAGE_SIZE, "token": "cursor-2"}),
        ]


@pytest.mark.asyncio
async def test_get_all_services_yields_services_from_every_page(
    mock_komodor_client: KomodorClient,
) -> None:
    with patch.object(
        mock_komodor_client, "_send_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            service_page("1", next_token="cursor-1"),
            service_page("2", next_token="cursor-2"),
            service_page("3"),
        ]

        services = await collect_services(mock_komodor_client)

        assert services == [
            {"id": "1", "type": "deployment"},
            {"id": "2", "type": "deployment"},
            {"id": "3", "type": "deployment"},
        ]


@pytest.mark.asyncio
async def test_get_all_services_stops_when_token_is_null(
    mock_komodor_client: KomodorClient,
) -> None:
    with patch.object(
        mock_komodor_client, "_send_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [service_page("1")]

        await collect_services(mock_komodor_client)

        assert mock_request.call_count == 1


@pytest.mark.asyncio
async def test_get_all_services_stops_when_token_key_is_absent(
    mock_komodor_client: KomodorClient,
) -> None:
    last_page = service_page("1")
    del last_page["meta"]["token"]

    with patch.object(
        mock_komodor_client, "_send_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [last_page]

        await collect_services(mock_komodor_client)

        assert mock_request.call_count == 1


async def collect_services(client: KomodorClient) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    async for batch in client.get_all_services():
        services.extend(batch)
    return services


def service_page(service_id: str, next_token: Optional[str] = None) -> dict[str, Any]:
    """The API sends an explicit null token on the last page, rather than dropping the key."""
    return {
        "data": {"services": [{"id": service_id, "type": "deployment"}]},
        "meta": {"pageSize": SERVICES_PAGE_SIZE, "token": next_token},
    }


def search_call(pagination: dict[str, Any]) -> Any:
    return call(
        url=f"{API_URL}/services/search",
        data={"pagination": pagination},
        method="POST",
    )
