import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from newrelic_integration.core.service_levels import ServiceLevelsHandler, SLI_OBJECT


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to initialize the port_ocean context."""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {"new_relic_account_id": "test_account"}
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Fixture to create a mocked HTTP client."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.mark.asyncio
class TestServiceLevelsHandler:
    @pytest.fixture
    def service_levels_handler(
        self, mock_http_client: AsyncMock
    ) -> ServiceLevelsHandler:
        """Fixture to create an instance of ServiceLevelsHandler."""
        return ServiceLevelsHandler(mock_http_client)

    async def test_get_service_level_indicator_value_none_response(
        self,
        service_levels_handler: ServiceLevelsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test handling of None response in get_service_level_indicator_value."""
        # Patch render_query and send_graph_api_request to handle None
        with (
            patch(
                "newrelic_integration.core.service_levels.render_query",
                return_value="mocked-query",
            ),
            patch(
                "newrelic_integration.core.service_levels.send_graph_api_request",
                return_value=None,
            ),
        ):
            # Test the method
            result = await service_levels_handler.get_service_level_indicator_value(
                mock_http_client, "test_nrql"
            )

            # Assertions
            assert result == {}

    async def test_get_service_level_indicator_value_successful_response(
        self,
        service_levels_handler: ServiceLevelsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful response in get_service_level_indicator_value."""
        # Prepare a mock successful response
        mock_successful_response: Dict[str, Any] = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [{"result": 95.5, "count": 1000, "total": 50}]
                        }
                    }
                }
            }
        }

        # Patch render_query and send_graph_api_request to return mock data
        with (
            patch(
                "newrelic_integration.core.service_levels.render_query",
                return_value="mocked-query",
            ),
            patch(
                "newrelic_integration.core.service_levels.send_graph_api_request",
                return_value=mock_successful_response,
            ),
        ):
            # Test the method
            result = await service_levels_handler.get_service_level_indicator_value(
                mock_http_client, "test_nrql"
            )

            # Assertions
            assert result == {"result": 95.5, "count": 1000, "total": 50}

    async def test_enrich_slo_with_sli_and_tags_none_nrql(
        self,
        service_levels_handler: ServiceLevelsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test enriching service level object with None or missing NRQL."""
        # Test cases with type hint
        test_cases: List[Dict[str, Any]] = [
            # Case 1: Missing indicators
            {"serviceLevel": {}},
            # Case 2: Empty indicators
            {"serviceLevel": {"indicators": []}},
            # Case 3: Missing resultQueries
            {"serviceLevel": {"indicators": [{}]}},
            # Case 4: Missing NRQL
            {"serviceLevel": {"indicators": [{"resultQueries": {"indicator": {}}}]}},
        ]

        for service_level in test_cases:
            # Mock SLI value retrieval to handle potential errors
            with patch.object(
                service_levels_handler,
                "get_service_level_indicator_value",
                return_value={},
            ):
                # Patch format_tags to do nothing
                with patch(
                    "newrelic_integration.core.service_levels.format_tags"
                ) as mock_format_tags:
                    # Test the method
                    result = await service_levels_handler.enrich_slo_with_sli_and_tags(
                        service_level
                    )

                    # Assertions
                    assert result.get(SLI_OBJECT, {}) == {}
                    mock_format_tags.assert_called_once_with(service_level)

    async def test_extract_service_levels_none_response(
        self,
        service_levels_handler: ServiceLevelsHandler,
    ) -> None:
        """Test extracting service levels from a None or malformed response."""
        # Test cases with explicit type hint
        test_cases: List[Optional[Dict[str, Any]]] = [
            # None response
            None,
            # Empty dictionary
            {},
            # Partial dictionary
            {"data": {}},
            {"data": {"actor": {}}},
            {"data": {"actor": {"entitySearch": {}}}},
            {"data": {"actor": {"entitySearch": {"results": {}}}}},
        ]

        for mock_response in test_cases:
            # Test the static method
            cursor, entities = await ServiceLevelsHandler._extract_service_levels(
                mock_response or {}
            )

            # Assertions
            assert cursor is None
            assert entities == []

    async def test_extract_service_levels_successful_response(
        self,
        service_levels_handler: ServiceLevelsHandler,
    ) -> None:
        """Test extracting service levels from a successful response."""
        # Prepare a mock successful response
        mock_successful_response: Dict[str, Any] = {
            "data": {
                "actor": {
                    "entitySearch": {
                        "results": {
                            "nextCursor": "next_page_token",
                            "entities": [
                                {"guid": "service_level_1"},
                                {"guid": "service_level_2"},
                            ],
                        }
                    }
                }
            }
        }

        # Test the static method
        cursor, entities = await ServiceLevelsHandler._extract_service_levels(
            mock_successful_response
        )

        # Assertions
        assert cursor == "next_page_token"
        assert len(entities) == 2
        assert entities[0]["guid"] == "service_level_1"
        assert entities[1]["guid"] == "service_level_2"

    async def test_list_service_levels_empty_generator(
        self,
        service_levels_handler: ServiceLevelsHandler,
    ) -> None:
        """Test list_service_levels method with an empty generator."""

        # Create mock async generator with no items
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[AsyncMock, None]:
            # Empty generator
            return
            yield

        # Patch the paginated request method
        with patch(
            "newrelic_integration.core.service_levels.send_paginated_graph_api_request",
            new=mock_paginated_request,
        ):
            # Collect results
            results = []
            async for batch in service_levels_handler.list_service_levels():
                results.extend(batch)

            # Assertions
            assert len(results) == 0

    async def test_list_service_levels_multiple_batches(
        self,
        service_levels_handler: ServiceLevelsHandler,
    ) -> None:
        test_batches = [
            {"id": "1"},
            {"id": "2"},
            {"id": "3"},
            {"id": "4"},
            {"id": "5"},
            {"id": "6"},
        ]

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any], None]:
            # Yield individual items instead of batches
            for item in test_batches:
                yield item

        with patch(
            "newrelic_integration.core.service_levels.send_paginated_graph_api_request",
            new=mock_paginated_request,
        ):
            results = []
            async for batch in service_levels_handler.list_service_levels():
                results.extend(batch)

            assert len(results) == 6
            assert [item["id"] for item in results] == ["1", "2", "3", "4", "5", "6"]
