"""Tests for endpoint resolver utilities"""

from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from http_server.helpers.endpoint_resolver import (
    extract_path_parameters,
    validate_endpoint_parameters,
    generate_resolved_endpoints,
    query_api_for_parameters,
    resolve_dynamic_endpoints,
)
from http_server.overrides import (
    ApiPathParameter,
    HttpServerSelector,
)


class TestExtractPathParameters:
    """Test path parameter extraction from endpoint templates"""

    def test_extract_single_parameter(self) -> None:
        """Test extracting a single path parameter"""
        endpoint = "/api/v1/teams/{team_id}/members"
        result = extract_path_parameters(endpoint)
        assert result == ["team_id"]

    def test_extract_multiple_parameters(self) -> None:
        """Test extracting multiple path parameters"""
        endpoint = "/api/v1/orgs/{org_id}/teams/{team_id}/members"
        result = extract_path_parameters(endpoint)
        assert result == ["org_id", "team_id"]

    def test_extract_no_parameters(self) -> None:
        """Test endpoint with no parameters"""
        endpoint = "/api/v1/users"
        result = extract_path_parameters(endpoint)
        assert result == []

    def test_extract_parameters_with_underscores(self) -> None:
        """Test extracting parameters with underscores"""
        endpoint = "/api/v1/user_groups/{user_group_id}"
        result = extract_path_parameters(endpoint)
        assert result == ["user_group_id"]


class TestValidateEndpointParameters:
    """Test parameter validation"""

    def test_all_parameters_configured(self) -> None:
        """Test validation when all parameters are configured"""
        param_names = ["team_id", "org_id"]
        path_parameters = {"team_id": MagicMock(), "org_id": MagicMock()}
        result = validate_endpoint_parameters(param_names, path_parameters)
        assert result == []

    def test_missing_single_parameter(self) -> None:
        """Test validation with one missing parameter"""
        param_names = ["team_id", "org_id"]
        path_parameters = {"team_id": MagicMock()}
        result = validate_endpoint_parameters(param_names, path_parameters)
        assert result == ["org_id"]

    def test_missing_all_parameters(self) -> None:
        """Test validation with all parameters missing"""
        param_names = ["team_id", "org_id"]
        path_parameters: Dict[str, Any] = {}
        result = validate_endpoint_parameters(param_names, path_parameters)
        assert result == ["team_id", "org_id"]

    def test_empty_parameter_list(self) -> None:
        """Test validation with no parameters needed"""
        param_names: List[str] = []
        path_parameters: Dict[str, Any] = {}
        result = validate_endpoint_parameters(param_names, path_parameters)
        assert result == []


class TestGenerateResolvedEndpoints:
    """Test endpoint generation from templates"""

    def test_generate_single_endpoint(self) -> None:
        """Test generating a single resolved endpoint"""
        template = "/api/v1/teams/{team_id}/members"
        param_name = "team_id"
        values = ["team-123"]
        result = generate_resolved_endpoints(template, param_name, values)
        assert result == [("/api/v1/teams/team-123/members", {"team_id": "team-123"})]

    def test_generate_multiple_endpoints(self) -> None:
        """Test generating multiple resolved endpoints"""
        template = "/api/v1/teams/{team_id}/members"
        param_name = "team_id"
        values = ["team-1", "team-2", "team-3"]
        result = generate_resolved_endpoints(template, param_name, values)
        assert result == [
            ("/api/v1/teams/team-1/members", {"team_id": "team-1"}),
            ("/api/v1/teams/team-2/members", {"team_id": "team-2"}),
            ("/api/v1/teams/team-3/members", {"team_id": "team-3"}),
        ]

    def test_generate_with_numeric_values(self) -> None:
        """Test generating endpoints with numeric parameter values"""
        template = "/api/v1/users/{user_id}"
        param_name = "user_id"
        values = ["123", "456"]
        result = generate_resolved_endpoints(template, param_name, values)
        assert result == [
            ("/api/v1/users/123", {"user_id": "123"}),
            ("/api/v1/users/456", {"user_id": "456"}),
        ]

    def test_generate_empty_values(self) -> None:
        """Test generating with empty values list"""
        template = "/api/v1/teams/{team_id}/members"
        param_name = "team_id"
        values: List[str] = []
        result = generate_resolved_endpoints(template, param_name, values)
        assert result == []


@pytest.mark.asyncio
class TestQueryApiForParameters:
    """Test querying API for parameter values"""

    @patch("http_server.helpers.endpoint_resolver.init_client")
    @patch("http_server.helpers.endpoint_resolver.ocean")
    async def test_query_with_single_batch(
        self, mock_ocean: MagicMock, mock_init_client: MagicMock
    ) -> None:
        """Test querying API that returns a single batch"""
        # Setup mock client
        mock_client = AsyncMock()

        async def mock_fetch(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"id": "team-1", "name": "Team 1"},
                {"id": "team-2", "name": "Team 2"},
            ]

        mock_client.fetch_paginated_data = mock_fetch
        mock_init_client.return_value = mock_client

        # Setup mock JQ processor
        async def mock_search(data: Any, path: str) -> Any:
            if path == ".id":
                return data.get("id")
            return None

        mock_ocean.app.integration.entity_processor._search = mock_search

        # Create param config
        param_config = ApiPathParameter(
            endpoint="/api/teams",
            method="GET",
            field=".id",
            query_params={},
            headers={},
        )

        # Execute
        result = await query_api_for_parameters(param_config)

        # Assert
        assert result == ["team-1", "team-2"]
        mock_init_client.assert_called_once()

    @patch("http_server.helpers.endpoint_resolver.init_client")
    @patch("http_server.helpers.endpoint_resolver.ocean")
    async def test_query_with_filter(
        self, mock_ocean: MagicMock, mock_init_client: MagicMock
    ) -> None:
        """Test querying API with a filter applied"""
        # Setup mock client
        mock_client = AsyncMock()

        async def mock_fetch(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"id": "team-1", "active": True},
                {"id": "team-2", "active": False},
                {"id": "team-3", "active": True},
            ]

        mock_client.fetch_paginated_data = mock_fetch
        mock_init_client.return_value = mock_client

        # Setup mock JQ processor
        async def mock_search(data: Any, path: str) -> Any:
            if path == ".id":
                return data.get("id")
            if path == ".active":
                return data.get("active")
            return None

        mock_ocean.app.integration.entity_processor._search = mock_search

        # Create param config with filter
        param_config = ApiPathParameter(
            endpoint="/api/teams",
            method="GET",
            field=".id",
            filter=".active",
            query_params={},
            headers={},
        )

        # Execute
        result = await query_api_for_parameters(param_config)

        # Assert - only active teams
        assert result == ["team-1", "team-3"]

    @patch("http_server.helpers.endpoint_resolver.init_client")
    @patch("http_server.helpers.endpoint_resolver.ocean")
    async def test_query_with_empty_response(
        self, mock_ocean: MagicMock, mock_init_client: MagicMock
    ) -> None:
        """Test querying API that returns empty results"""
        # Setup mock client
        mock_client = AsyncMock()

        async def mock_fetch(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        mock_client.fetch_paginated_data = mock_fetch
        mock_init_client.return_value = mock_client

        # Create param config
        param_config = ApiPathParameter(
            endpoint="/api/teams",
            method="GET",
            field=".id",
            query_params={},
            headers={},
        )

        # Execute
        result = await query_api_for_parameters(param_config)

        # Assert
        assert result == []


@pytest.mark.asyncio
class TestResolveDynamicEndpoints:
    """Test the main endpoint resolution orchestrator"""

    async def test_static_endpoint_no_parameters(self) -> None:
        """Test resolving a static endpoint with no parameters"""
        selector = HttpServerSelector(query="true")
        kind = "/api/v1/users"

        result = await resolve_dynamic_endpoints(selector, kind)

        assert result == [("/api/v1/users", {})]

    async def test_empty_kind(self) -> None:
        """Test handling empty kind"""
        selector = HttpServerSelector(query="true")
        kind = ""

        result = await resolve_dynamic_endpoints(selector, kind)

        assert result == []

    async def test_missing_path_parameters_config(self) -> None:
        """Test endpoint with parameters but missing configuration"""
        selector = HttpServerSelector(query="true")
        kind = "/api/v1/teams/{team_id}/members"

        result = await resolve_dynamic_endpoints(selector, kind)

        # Returns the template as-is when config is missing
        assert result == [("/api/v1/teams/{team_id}/members", {})]

    @patch("http_server.helpers.endpoint_resolver.query_api_for_parameters")
    async def test_resolve_with_single_parameter(self, mock_query: AsyncMock) -> None:
        """Test resolving endpoint with a single path parameter"""
        # Setup mock query response
        mock_query.return_value = ["team-1", "team-2"]

        # Create selector with path parameters
        param_config = ApiPathParameter(
            endpoint="/api/teams",
            method="GET",
            field=".id",
            query_params={},
            headers={},
        )

        selector = HttpServerSelector(
            query="true", path_parameters={"team_id": param_config}
        )
        kind = "/api/v1/teams/{team_id}/members"

        # Execute
        result = await resolve_dynamic_endpoints(selector, kind)

        # Assert
        assert result == [
            ("/api/v1/teams/team-1/members", {"team_id": "team-1"}),
            ("/api/v1/teams/team-2/members", {"team_id": "team-2"}),
        ]
        mock_query.assert_called_once_with(param_config)

    @patch("http_server.helpers.endpoint_resolver.query_api_for_parameters")
    async def test_resolve_with_no_values_found(self, mock_query: AsyncMock) -> None:
        """Test resolving when API returns no parameter values"""
        # Setup mock query to return empty list
        mock_query.return_value = []

        # Create selector with path parameters
        param_config = ApiPathParameter(
            endpoint="/api/teams",
            method="GET",
            field=".id",
            query_params={},
            headers={},
        )

        selector = HttpServerSelector(
            query="true", path_parameters={"team_id": param_config}
        )
        kind = "/api/v1/teams/{team_id}/members"

        # Execute
        result = await resolve_dynamic_endpoints(selector, kind)

        # Assert - returns empty list when no values found
        assert result == []

    @patch("http_server.helpers.endpoint_resolver.query_api_for_parameters")
    async def test_resolve_with_multiple_parameters_warns(
        self, mock_query: AsyncMock
    ) -> None:
        """Test resolving endpoint with multiple parameters (currently only handles first)"""
        # Setup mock query response
        mock_query.return_value = ["org-1"]

        # Create selector with multiple path parameters
        org_param = ApiPathParameter(
            endpoint="/api/orgs",
            method="GET",
            field=".id",
            query_params={},
            headers={},
        )
        team_param = ApiPathParameter(
            endpoint="/api/teams",
            method="GET",
            field=".id",
            query_params={},
            headers={},
        )

        selector = HttpServerSelector(
            query="true",
            path_parameters={"org_id": org_param, "team_id": team_param},
        )
        kind = "/api/v1/orgs/{org_id}/teams/{team_id}/members"

        # Execute
        result = await resolve_dynamic_endpoints(selector, kind)

        # Assert - only first parameter is resolved (current limitation)
        assert result == [
            ("/api/v1/orgs/org-1/teams/{team_id}/members", {"org_id": "org-1"})
        ]
        mock_query.assert_called_once()
