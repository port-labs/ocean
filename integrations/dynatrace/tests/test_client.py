import pytest
from unittest.mock import AsyncMock

from client import DynatraceClient
from port_ocean.context.ocean import ocean
from port_ocean.ocean import Ocean


@pytest.fixture(autouse=True)
def setup_ocean():
    app = Ocean()
    ocean.set_app(app)


@pytest.mark.asyncio
async def test_enrich_slos_with_related_entities():
    """
    Tests that enrich_slos_with_related_entities correctly adds the
    __relatedEntities key to each SLO based on the entities returned
    by _get_slo_related_entities.
    """
    client = DynatraceClient(host_url="http://test.com", api_key="test_key")

    slos_to_enrich = [
        {"id": "slo-1"},
        {"id": "slo-2"},
    ]

    related_entities_slo_1 = [{"entityId": "SERVICE-123"}]
    related_entities_slo_2 = [{"entityId": "HOST-456"}]

    # Mock the internal method that fetches related entities
    client._get_slo_related_entities = AsyncMock(
        side_effect=[related_entities_slo_1, related_entities_slo_2]
    )

    enriched_slos = await client.enrich_slos_with_related_entities(slos_to_enrich)

    expected_slos = [
        {"id": "slo-1", "__relatedEntities": related_entities_slo_1},
        {"id": "slo-2", "__relatedEntities": related_entities_slo_2},
    ]

    assert enriched_slos == expected_slos
    assert client._get_slo_related_entities.call_count == 2


@pytest.mark.asyncio
async def test_enrich_slos_with_related_entities_exception():
    """
    Tests that enrich_slos_with_related_entities correctly propagates an
    exception if _get_slo_related_entities raises one.
    """
    client = DynatraceClient(host_url="http://test.com", api_key="test_key")

    slos_to_enrich = [
        {"id": "slo-1"},
    ]

    # Mock the internal method to raise an exception
    client._get_slo_related_entities = AsyncMock(side_effect=Exception("API Error"))

    with pytest.raises(Exception, match="API Error"):
        await client.enrich_slos_with_related_entities(slos_to_enrich)

    assert client._get_slo_related_entities.call_count == 1
