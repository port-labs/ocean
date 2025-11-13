import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from typing import Dict, Any, List, Optional

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from newrelic_integration.core.alert_conditions import AlertConditionsHandler


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to initialize the port_ocean context."""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "new_relic_api_key": "test_api_key",
            "new_relic_rest_api_url": "https://api.newrelic.com",
        }
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
class TestAlertConditionsHandler:
    @pytest.fixture
    def alert_conditions_handler(
        self, mock_http_client: AsyncMock
    ) -> AlertConditionsHandler:
        """Fixture to create an instance of AlertConditionsHandler."""
        return AlertConditionsHandler(mock_http_client)

    async def test_fetch_tags_for_entity_success(
        self,
        alert_conditions_handler: AlertConditionsHandler,
    ) -> None:
        """Test successful retrieval of tags for an entity."""
        mock_response: Dict[str, Any] = {
            "data": {
                "actor": {
                    "entity": {
                        "guid": "test-guid",
                        "name": "Test Entity",
                        "tags": [
                            {"key": "environment", "values": ["production"]},
                            {"key": "team", "values": ["backend"]},
                        ],
                    }
                }
            }
        }

        with (
            patch(
                "newrelic_integration.core.alert_conditions.render_query",
                return_value="test-query",
            ),
            patch(
                "newrelic_integration.core.alert_conditions.send_graph_api_request",
                return_value=mock_response,
            ),
        ):
            tags = await alert_conditions_handler.fetch_tags_for_entity("test-guid")

            assert len(tags) == 2
            assert tags[0]["key"] == "environment"
            assert tags[0]["values"] == ["production"]
            assert tags[1]["key"] == "team"
            assert tags[1]["values"] == ["backend"]

    async def test_fetch_tags_for_entity_empty_guid(
        self,
        alert_conditions_handler: AlertConditionsHandler,
    ) -> None:
        """Test fetching tags with empty entity GUID."""
        tags = await alert_conditions_handler.fetch_tags_for_entity("")
        assert tags == []

    async def test_fetch_tags_for_entity_no_entity_found(
        self,
        alert_conditions_handler: AlertConditionsHandler,
    ) -> None:
        """Test when entity is not found."""
        mock_response: Dict[str, Any] = {"data": {"actor": {"entity": None}}}

        with (
            patch(
                "newrelic_integration.core.alert_conditions.render_query",
                return_value="test-query",
            ),
            patch(
                "newrelic_integration.core.alert_conditions.send_graph_api_request",
                return_value=mock_response,
            ),
        ):
            tags = await alert_conditions_handler.fetch_tags_for_entity(
                "non-existent-guid"
            )
            assert tags == []

    async def test_fetch_tags_for_entity_exception_handling(
        self,
        alert_conditions_handler: AlertConditionsHandler,
    ) -> None:
        """Test exception handling when fetching tags."""
        with (
            patch(
                "newrelic_integration.core.alert_conditions.render_query",
                return_value="test-query",
            ),
            patch(
                "newrelic_integration.core.alert_conditions.send_graph_api_request",
                side_effect=Exception("API Error"),
            ),
        ):
            tags = await alert_conditions_handler.fetch_tags_for_entity("test-guid")
            assert tags == []

    async def test_list_alert_policies_success(
        self,
        alert_conditions_handler: AlertConditionsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful retrieval of alert policies."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "policies": [
                {"id": 123, "name": "Policy 1"},
                {"id": 456, "name": "Policy 2"},
            ]
        }
        mock_http_client.get.return_value = mock_response

        policies = await alert_conditions_handler.list_alert_policies()

        assert len(policies) == 2
        assert 123 in policies
        assert 456 in policies
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert "v2/alerts_policies.json" in call_args[0][0]

    async def test_list_alert_policies_empty_response(
        self,
        alert_conditions_handler: AlertConditionsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test when no policies are returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"policies": []}
        mock_http_client.get.return_value = mock_response

        policies = await alert_conditions_handler.list_alert_policies()

        assert policies == []

    async def test_list_alert_conditions_for_policy_success(
        self,
        alert_conditions_handler: AlertConditionsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful retrieval of alert conditions for a policy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = MagicMock()
        mock_response.headers.get.return_value = None
        mock_response.json.return_value = {
            "nrql_conditions": [
                {
                    "id": 789,
                    "name": "Condition 1",
                    "enabled": True,
                    "entity_guid": "entity-guid-1",
                },
                {
                    "id": 790,
                    "name": "Condition 2",
                    "enabled": False,
                    "entity_guid": None,
                },
            ]
        }
        mock_http_client.get.return_value = mock_response

        conditions = await alert_conditions_handler.list_alert_conditions_for_policy(
            123
        )

        assert len(conditions) == 2
        assert conditions[0]["id"] == 789
        assert conditions[0]["name"] == "Condition 1"
        assert conditions[1]["id"] == 790
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert "v2/alerts_nrql_conditions.json" in call_args[0][0]
        assert call_args[1]["params"]["policy_id"] == 123

    async def test_list_alert_conditions_for_policy_alternative_format(
        self,
        alert_conditions_handler: AlertConditionsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test handling of alternative response format (conditions instead of nrql_conditions)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = MagicMock()
        mock_response.headers.get.return_value = None
        mock_response.json.return_value = {
            "conditions": [{"id": 999, "name": "Condition Alternative Format"}]
        }
        mock_http_client.get.return_value = mock_response

        conditions = await alert_conditions_handler.list_alert_conditions_for_policy(
            123
        )

        assert len(conditions) == 1
        assert conditions[0]["id"] == 999

    async def test_list_alert_conditions_for_policy_error_response(
        self,
        alert_conditions_handler: AlertConditionsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test handling of error response from API."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = MagicMock()
        mock_response.headers.get.return_value = None
        mock_response.json.return_value = {
            "error": {
                "title": "Policy not found",
                "message": "Policy 999 does not exist",
            }
        }
        mock_http_client.get.return_value = mock_response

        conditions = await alert_conditions_handler.list_alert_conditions_for_policy(
            999
        )

        assert conditions == []

    async def test_list_alert_conditions_for_policy_empty_response(
        self,
        alert_conditions_handler: AlertConditionsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test when no conditions are returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = MagicMock()
        mock_response.headers.get.return_value = None
        mock_response.json.return_value = {}
        mock_http_client.get.return_value = mock_response

        conditions = await alert_conditions_handler.list_alert_conditions_for_policy(
            123
        )

        assert conditions == []

    async def test_list_alert_conditions_for_policy_with_pagination(
        self,
        alert_conditions_handler: AlertConditionsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test pagination handling when multiple pages are returned."""
        # First page response
        first_page_response = MagicMock()
        first_page_response.status_code = 200
        first_page_headers = MagicMock()

        # Make headers.get return the Link header for "Link" or "link", None otherwise
        def first_page_headers_get(key: str) -> Optional[str]:
            if key.lower() == "link":
                return '<https://api.newrelic.com/v2/alerts_nrql_conditions.json?policy_id=123&page=2>; rel="next"'
            return None

        first_page_headers.get.side_effect = first_page_headers_get
        first_page_response.headers = first_page_headers
        first_page_response.json.return_value = {
            "nrql_conditions": [
                {"id": 1, "name": "Condition 1"},
                {"id": 2, "name": "Condition 2"},
            ]
        }

        # Second page response (last page)
        second_page_response = MagicMock()
        second_page_response.status_code = 200
        second_page_headers = MagicMock()
        second_page_headers.get.return_value = None  # No next page
        second_page_response.headers = second_page_headers
        second_page_response.json.return_value = {
            "nrql_conditions": [
                {"id": 3, "name": "Condition 3"},
            ]
        }

        # Mock the get method to return different responses for different calls
        mock_http_client.get.side_effect = [first_page_response, second_page_response]

        conditions = await alert_conditions_handler.list_alert_conditions_for_policy(
            123
        )

        assert len(conditions) == 3
        assert conditions[0]["id"] == 1
        assert conditions[1]["id"] == 2
        assert conditions[2]["id"] == 3
        # Verify that get was called twice (once for each page)
        assert mock_http_client.get.call_count == 2

    async def test_enrich_condition_with_tags_with_entity_guid(
        self,
        alert_conditions_handler: AlertConditionsHandler,
    ) -> None:
        """Test enriching condition with tags when entity_guid is present."""
        condition: Dict[str, Any] = {
            "id": 123,
            "name": "Test Condition",
            "entity_guid": "test-entity-guid",
        }

        mock_tags = [
            {"key": "environment", "values": ["production"]},
            {"key": "team", "values": ["backend"]},
        ]

        with patch.object(
            alert_conditions_handler,
            "fetch_tags_for_entity",
            return_value=mock_tags,
        ):
            enriched = await alert_conditions_handler.enrich_condition_with_tags(
                condition
            )

            assert enriched["tags"] == {
                "environment": ["production"],
                "team": ["backend"],
            }
            assert enriched["id"] == 123
            assert enriched["name"] == "Test Condition"

    async def test_enrich_condition_with_tags_without_entity_guid(
        self,
        alert_conditions_handler: AlertConditionsHandler,
    ) -> None:
        """Test enriching condition when entity_guid is not present."""
        condition: Dict[str, Any] = {
            "id": 123,
            "name": "Test Condition",
        }

        enriched = await alert_conditions_handler.enrich_condition_with_tags(condition)

        assert enriched["tags"] == {}
        assert enriched["id"] == 123

    async def test_list_alert_conditions_success(
        self,
        alert_conditions_handler: AlertConditionsHandler,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test listing all alert conditions with multiple policies."""
        # Mock list_alert_policies
        with patch.object(
            alert_conditions_handler,
            "list_alert_policies",
            return_value=[123, 456],
        ):
            # Mock list_alert_conditions_for_policy for each policy
            async def mock_list_conditions(policy_id: int) -> List[Dict[str, Any]]:
                if policy_id == 123:
                    return [
                        {
                            "id": 1,
                            "name": "Condition 1",
                            "entity_guid": "guid-1",
                        }
                    ]
                elif policy_id == 456:
                    return [
                        {
                            "id": 2,
                            "name": "Condition 2",
                            "entity_guid": None,
                        }
                    ]
                return []

            with patch.object(
                alert_conditions_handler,
                "list_alert_conditions_for_policy",
                side_effect=mock_list_conditions,
            ):
                with patch.object(
                    alert_conditions_handler,
                    "enrich_condition_with_tags",
                    side_effect=lambda c: {**c, "tags": {}},
                ):
                    conditions: List[Dict[str, Any]] = [
                        condition
                        async for condition in alert_conditions_handler.list_alert_conditions()
                    ]

                    assert len(conditions) == 2
                    assert conditions[0]["id"] == 1
                    assert conditions[0]["policy_id"] == 123
                    assert conditions[1]["id"] == 2
                    assert conditions[1]["policy_id"] == 456

    async def test_list_alert_conditions_empty_policies(
        self,
        alert_conditions_handler: AlertConditionsHandler,
    ) -> None:
        """Test listing alert conditions when no policies exist."""
        with patch.object(
            alert_conditions_handler,
            "list_alert_policies",
            return_value=[],
        ):
            conditions: List[Dict[str, Any]] = [
                condition
                async for condition in alert_conditions_handler.list_alert_conditions()
            ]

            assert len(conditions) == 0

    async def test_list_alert_conditions_policy_with_no_conditions(
        self,
        alert_conditions_handler: AlertConditionsHandler,
    ) -> None:
        """Test listing alert conditions when a policy has no conditions."""
        with patch.object(
            alert_conditions_handler,
            "list_alert_policies",
            return_value=[123],
        ):
            with patch.object(
                alert_conditions_handler,
                "list_alert_conditions_for_policy",
                return_value=[],
            ):
                conditions: List[Dict[str, Any]] = [
                    condition
                    async for condition in alert_conditions_handler.list_alert_conditions()
                ]

                assert len(conditions) == 0
