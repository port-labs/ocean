import pytest
from unittest.mock import AsyncMock, MagicMock

from checkmarx_one.core.exporters.application_exporter import CheckmarxApplicationExporter
from checkmarx_one.core.options import ListApplicationOptions, SingleApplicationOptions


class TestCheckmarxApplicationExporter:
    """Tests for CheckmarxApplicationExporter."""

    @pytest.fixture
    def mock_client(self):
        """Mock Checkmarx client."""
        client = MagicMock()
        client.send_api_request = AsyncMock()
        client.send_paginated_request = AsyncMock()
        return client

    @pytest.fixture
    def application_exporter(self, mock_client):
        """Application exporter fixture."""
        return CheckmarxApplicationExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_resource(self, application_exporter, mock_client):
        """Test getting a single application resource."""
        # Arrange
        application_id = "test-app-123"
        expected_response = {
            "id": application_id,
            "name": "Test Application",
            "criticality": 3
        }
        mock_client.send_api_request.return_value = expected_response
        options = SingleApplicationOptions(application_id=application_id)

        # Act
        result = await application_exporter.get_resource(options)

        # Assert
        assert result == expected_response
        mock_client.send_api_request.assert_called_once_with(f"/applications/{application_id}")

    @pytest.mark.asyncio
    async def test_get_paginated_resources_no_filters(self, application_exporter, mock_client):
        """Test getting paginated applications without filters."""
        # Arrange
        expected_applications = [
            {"id": "app-1", "name": "App 1", "criticality": 1},
            {"id": "app-2", "name": "App 2", "criticality": 2}
        ]
        
        async def mock_paginated_request(endpoint, object_key, params):
            yield expected_applications

        mock_client.send_paginated_request = mock_paginated_request
        options = ListApplicationOptions()

        # Act
        results = []
        async for batch in application_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert results == expected_applications

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_criticality_filter(self, application_exporter, mock_client):
        """Test getting paginated applications with criticality filter."""
        # Arrange
        expected_applications = [
            {"id": "app-1", "name": "Critical App", "criticality": 3}
        ]
        
        async def mock_paginated_request(endpoint, object_key, params):
            assert params == {"criticality": [3]}
            yield expected_applications

        mock_client.send_paginated_request = mock_paginated_request
        options = ListApplicationOptions(criticality=[3])

        # Act
        results = []
        async for batch in application_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert results == expected_applications

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_result(self, application_exporter, mock_client):
        """Test handling empty results from paginated request."""
        # Arrange
        async def mock_paginated_request(endpoint, object_key, params):
            yield []

        mock_client.send_paginated_request = mock_paginated_request
        options = ListApplicationOptions()

        # Act
        results = []
        async for batch in application_exporter.get_paginated_resources(options):
            results.extend(batch)

        # Assert
        assert results == []