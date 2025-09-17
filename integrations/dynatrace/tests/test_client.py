import pytest
from unittest.mock import AsyncMock, MagicMock
from pytest import MonkeyPatch

from client import DynatraceClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def setup_ocean() -> None:
    try:
        mock_ocean_app = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
async def test_enrich_slos_with_related_entities(monkeypatch: MonkeyPatch) -> None:
    """
    Tests that enrich_slos_with_related_entities correctly adds the
    __entities key to each SLO based on the entities returned
    by _get_slo_related_entities.
    """
    client = DynatraceClient(host_url="http://test.com", api_key="test_key")

    slos_to_enrich = [
        {"id": "slo-1", "name": "slo-1-name", "filter": "filter-1"},
        {"id": "slo-2", "name": "slo-2-name", "filter": "filter-2"},
    ]

    related_entities_slo_1 = [{"entityId": "SERVICE-123"}]
    related_entities_slo_2 = [{"entityId": "HOST-456"}]

    # Mock the internal method that fetches related entities
    mock_get_related_entities = AsyncMock(
        side_effect=[related_entities_slo_1, related_entities_slo_2]
    )
    monkeypatch.setattr(
        client,
        "_get_slo_related_entities",
        mock_get_related_entities,
    )

    enriched_slos = await client.enrich_slos_with_related_entities(slos_to_enrich)

    expected_slos = [
        {"id": "slo-1", "name": "slo-1-name", "filter": "filter-1", "__entities": related_entities_slo_1},
        {"id": "slo-2", "name": "slo-2-name", "filter": "filter-2", "__entities": related_entities_slo_2},
    ]

    assert enriched_slos == expected_slos
    assert mock_get_related_entities.call_count == 2


@pytest.mark.asyncio
async def test_enrich_slos_with_related_entities_exception(
    monkeypatch: MonkeyPatch,
) -> None:
    """
    Tests that enrich_slos_with_related_entities handles exceptions gracefully
    and does not add the `__entities` key to an SLO if fetching its related
    entities fails.
    """
    client = DynatraceClient(host_url="http://test.com", api_key="test_key")

    slos_to_enrich = [
        {"id": "slo-1", "name": "slo-1-name", "filter": "filter-1"},
    ]

    # Mock the internal method to raise an exception
    mock_get_related_entities = AsyncMock(side_effect=Exception("API Error"))
    monkeypatch.setattr(client, "_get_slo_related_entities", mock_get_related_entities)

    enriched_slos = await client.enrich_slos_with_related_entities(slos_to_enrich)

    assert enriched_slos == slos_to_enrich
    assert mock_get_related_entities.call_count == 1


@pytest.mark.asyncio
async def test_enrich_slos_with_empty_or_missing_filter(
    monkeypatch: MonkeyPatch,
) -> None:
    """
    Tests that enrich_slos_with_related_entities correctly handles SLOs
    with an empty or missing filter. It should not attempt to fetch
    entities for such SLOs.
    """
    client = DynatraceClient(host_url="http://test.com", api_key="test_key")

    slos_to_enrich = [
        {"id": "slo-1", "name": "slo-1-name", "filter": "filter-1"},
        {"id": "slo-2", "name": "slo-2-name", "filter": ""},  # SLO with empty filter
        {"id": "slo-3", "name": "slo-3-name"},  # SLO without filter
    ]

    related_entities_slo_1 = [{"entityId": "SERVICE-123"}]

    # Mock the internal method that fetches related entities
    mock_get_related_entities = AsyncMock(side_effect=[related_entities_slo_1])
    monkeypatch.setattr(
        client,
        "_get_slo_related_entities",
        mock_get_related_entities,
    )

    enriched_slos = await client.enrich_slos_with_related_entities(slos_to_enrich)

    expected_slos = [
        {"id": "slo-1", "name": "slo-1-name", "filter": "filter-1", "__entities": related_entities_slo_1},
        {"id": "slo-2", "name": "slo-2-name", "filter": ""},
        {"id": "slo-3", "name": "slo-3-name"},
    ]

    assert enriched_slos == expected_slos
    assert mock_get_related_entities.call_count == 1
    mock_get_related_entities.assert_called_once_with("filter-1")
