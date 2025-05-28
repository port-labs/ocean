import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from newrelic_integration.core.errors import NewRelicNotFoundError
from newrelic_integration.core.entities import EntitiesHandler
from typing import AsyncGenerator, List, Dict, Any


# Fixture to mock the Ocean context initialization
@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to initialize the port_ocean context."""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {"some_config": "value"}
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


# Helper fixture for creating mock HTTP client
@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Fixture to return a mocked HTTP client."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
async def mock_send_request() -> AsyncGenerator[AsyncMock, None]:
    """Fixture to mock send_graph_api_request function."""
    with patch(
        "newrelic_integration.core.entities.send_graph_api_request",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


# Fixture to mock the render_query function in EntitiesHandler
@pytest.fixture
async def mock_render_query() -> AsyncGenerator[AsyncMock, None]:
    """Fixture to mock render_query function."""
    with patch(
        "newrelic_integration.core.entities.render_query", new_callable=AsyncMock
    ) as mock:
        yield mock


# Test class using async test cases
@pytest.mark.asyncio
class TestEntitiesHandler:

    @pytest.fixture
    def entities_handler(self, mock_http_client: AsyncMock) -> EntitiesHandler:
        """Fixture to create an instance of EntitiesHandler."""
        return EntitiesHandler(mock_http_client)

    async def test_get_entity_success(
        self,
        entities_handler: EntitiesHandler,
        mock_send_request: AsyncMock,
        mock_render_query: AsyncMock,
    ) -> None:
        """Test successful retrieval of an entity."""
        mock_response: Dict[str, Any] = {
            "data": {
                "actor": {
                    "entity": {
                        "guid": "test-guid",
                        "name": "Test Entity",
                        "tags": [{"key": "test", "values": ["value"]}],
                    }
                }
            }
        }

        # Setup mocks
        mock_send_request.return_value = mock_response
        mock_render_query.return_value = "test-query"

        # Test the method under test
        entity = await entities_handler.get_entity("test-guid")

        # Assertions
        assert entity["guid"] == "test-guid"
        assert entity["name"] == "Test Entity"
        assert entity["tags"] == {"test": ["value"]}

    async def test_get_entity_not_found(
        self,
        entities_handler: EntitiesHandler,
        mock_send_request: AsyncMock,
        mock_render_query: AsyncMock,
    ) -> None:
        """Test when an entity is not found."""
        mock_response: Dict[str, Any] = {"data": {"actor": {"entity": {}}}}

        # Setup mocks
        mock_send_request.return_value = mock_response
        mock_render_query.return_value = "test-query"

        # Expect exception
        with pytest.raises(NewRelicNotFoundError):
            await entities_handler.get_entity("non-existent-guid")

    async def test_list_entities_by_resource_kind(
        self,
        entities_handler: EntitiesHandler,
        mock_send_request: AsyncMock,
        mock_render_query: AsyncMock,
    ) -> None:
        """Test listing entities by resource kind."""

        async def mock_async_generator(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Dict[str, Any], None]:
            test_entity: Dict[str, Any] = {
                "guid": "entity1",
                "name": "Entity 1",
                "tags": [{"key": "key1", "values": ["value1"]}],
            }
            yield test_entity

        # Mock resource configuration
        with patch(
            "newrelic_integration.core.entities.get_port_resource_configuration_by_port_kind"
        ) as mock_config:
            mock_config.return_value = MagicMock(
                selector=MagicMock(
                    entity_query_filter="test-filter",
                    entity_extra_properties_query=None,
                )
            )

            with patch(
                "newrelic_integration.core.entities.send_paginated_graph_api_request",
                new=mock_async_generator,
            ):
                entities: List[Dict[str, Any]] = [
                    entity
                    async for entity in entities_handler.list_entities_by_resource_kind(
                        "test-resource"
                    )
                ]

                # Assertions
                assert len(entities) == 1
                assert entities[0]["guid"] == "entity1"
                assert entities[0]["tags"] == {"key1": ["value1"]}

    async def test_list_entities_by_guids(
        self,
        entities_handler: EntitiesHandler,
        mock_send_request: AsyncMock,
        mock_render_query: AsyncMock,
    ) -> None:
        """Test listing entities by their GUIDs."""
        mock_response: Dict[str, Any] = {
            "data": {
                "actor": {
                    "entities": [
                        {
                            "guid": "entity1",
                            "name": "Entity 1",
                            "tags": [{"key": "test", "values": ["value"]}],
                        }
                    ]
                }
            }
        }

        # Setup mocks
        mock_send_request.return_value = mock_response
        mock_render_query.return_value = "test-query"

        # Call the method under test
        entities: List[Dict[str, Any]] = await entities_handler.list_entities_by_guids(
            mock_send_request, ["entity1"]
        )
        # Assertions
        assert len(entities) == 1
        assert entities[0]["guid"] == "entity1"
        assert entities[0]["tags"] == {"test": ["value"]}

    async def test_list_entities_by_resource_kind_none_response(
        self,
        entities_handler: EntitiesHandler,
        mock_send_request: AsyncMock,
        mock_render_query: AsyncMock,
    ) -> None:
        """Test when the response is None in the paginated query."""

        async def mock_async_generator(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Dict[str, Any], None]:
            yield {}

        # Mock resource configuration
        with patch(
            "newrelic_integration.core.entities.get_port_resource_configuration_by_port_kind"
        ) as mock_config:
            mock_config.return_value = MagicMock(
                selector=MagicMock(
                    entity_query_filter="test-filter",
                    entity_extra_properties_query=None,
                )
            )

            with patch(
                "newrelic_integration.core.entities.send_paginated_graph_api_request",
                new=mock_async_generator,
            ):
                entities: List[Dict[str, Any]] = [
                    entity
                    async for entity in entities_handler.list_entities_by_resource_kind(
                        "test-resource"
                    )
                ]

                # Assertions
                assert len(entities) == 0

    async def test_list_entities_by_resource_kind_empty_response(
        self,
        entities_handler: EntitiesHandler,
        mock_send_request: AsyncMock,
        mock_render_query: AsyncMock,
    ) -> None:
        """Test when the response is empty in the paginated query."""

        async def mock_async_generator(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Dict[str, Any], None]:
            yield {}

        # Mock resource configuration
        with patch(
            "newrelic_integration.core.entities.get_port_resource_configuration_by_port_kind"
        ) as mock_config:
            mock_config.return_value = MagicMock(
                selector=MagicMock(
                    entity_query_filter="test-filter",
                    entity_extra_properties_query=None,
                )
            )

            with patch(
                "newrelic_integration.core.entities.send_paginated_graph_api_request",
                new=mock_async_generator,
            ):
                entities: List[Dict[str, Any]] = [
                    entity
                    async for entity in entities_handler.list_entities_by_resource_kind(
                        "test-resource"
                    )
                ]

                # Assertions
                assert len(entities) == 0

    async def test_get_entity_none_response(
        self,
        entities_handler: EntitiesHandler,
        mock_send_request: AsyncMock,
        mock_render_query: AsyncMock,
    ) -> None:
        """Test when no entity is found (None or empty response)."""
        mock_response: Dict[str, Any] = {
            "data": {"actor": {"entity": None}}  # Represents no entity
        }

        # Setup mocks
        mock_send_request.return_value = mock_response
        mock_render_query.return_value = "test-query"

        # Expect exception
        with pytest.raises(NewRelicNotFoundError):
            await entities_handler.get_entity("non-existent-guid")
