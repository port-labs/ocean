from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.defaults.common import Defaults
from port_ocean.core.defaults.initialize import _create_resources
from port_ocean.core.models import Blueprint


@pytest.fixture
def mock_defaults() -> Defaults:
    """Create a mock Defaults object with sample data."""
    return Defaults(
        blueprints=[
            {
                "identifier": "blueprint1",
                "title": "Blueprint 1",
                "icon": "Microservice",
                "schema": {"type": "object", "properties": {}},
                "relations": {},
                "calculationProperties": {},
                "mirrorProperties": {},
                "aggregationProperties": {},
                "teamInheritance": {},
                "ownership": {},
            },
            {
                "identifier": "blueprint2",
                "title": "Blueprint 2",
                "icon": "Microservice",
                "schema": {"type": "object", "properties": {}},
                "relations": {},
                "calculationProperties": {},
                "mirrorProperties": {},
                "aggregationProperties": {},
                "teamInheritance": {},
                "ownership": {},
            },
        ],
        actions=[
            {"identifier": "action1", "title": "Action 1"},
            {"identifier": "action2", "title": "Action 2"},
        ],
        scorecards=[
            {"blueprint": "blueprint1", "data": [{"identifier": "scorecard1"}]},
        ],
        pages=[
            {"identifier": "page1", "title": "Page 1"},
        ],
    )


@pytest.fixture
def mock_port_client() -> PortClient:
    """Create a mock PortClient."""
    mock_client = MagicMock(spec=PortClient)
    mock_client.get_blueprint = AsyncMock()
    mock_client.get_current_integration = AsyncMock()
    mock_client.create_blueprint = AsyncMock()
    mock_client.patch_blueprint = AsyncMock()
    mock_client.create_action = AsyncMock()
    mock_client.create_scorecard = AsyncMock()
    mock_client.create_page = AsyncMock()
    return mock_client


@pytest.mark.asyncio
async def test_create_resources_all_mapped_blueprints_exist(
    mock_port_client: PortClient, mock_defaults: Defaults
) -> None:
    """
    Test case 1: All mapped blueprints exist in Port and they are different from default ones.
    Should skip creation of all resources.

    Flow:
    1. Get_blueprint is called for creation_stage default blueprints
       - These should NOT exist (raise exception) so blueprints_results = []
    2. _mapped_blueprints_exist calls get_blueprint for mapped blueprints
       - These SHOULD exist (return Blueprint) so mapped_blueprints_exist = True
    3. Since mapped_blueprints_exist is True, we skip creation
    """
    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "config": {
            "resources": [
                {
                    "port": {
                        "entity": {
                            "mappings": {
                                "blueprint": "blueprint1test",
                            }
                        }
                    }
                },
                {
                    "port": {
                        "entity": {
                            "mappings": {
                                "blueprint": "blueprint2test",
                            }
                        }
                    }
                },
            ]
        }
    }

    # Track call order: first 2 calls are for creation_stage, next 2 are for mapped blueprints
    call_count = 0

    async def get_blueprint_side_effect(
        identifier: str, should_log: bool = True
    ) -> Blueprint:
        nonlocal call_count
        call_count += 1

        # First 2 calls are for creation_stage blueprints
        # These should NOT exist to make blueprints_results = []
        if call_count <= 2:
            raise Exception(f"Blueprint {identifier} not found")

        # Next 2 calls are for mapped blueprints
        # These SHOULD exist to make mapped_blueprints_exist = True
        return Blueprint.parse_obj(
            {
                "identifier": identifier,
                "title": f"Blueprint {identifier}",
                "team": None,
                "schema": {"type": "object", "properties": {}},
                "relations": {},
            }
        )

    mock_port_client.get_blueprint.side_effect = get_blueprint_side_effect  # type: ignore[attr-defined]

    # Execute
    await _create_resources(
        mock_port_client, mock_defaults, has_provision_feature_flag=False
    )

    # Assert: Should not create any blueprints, actions, scorecards, or pages
    mock_port_client.create_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.patch_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_action.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_scorecard.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_page.assert_not_called()  # type: ignore[attr-defined]
    assert mock_port_client.get_blueprint.call_count == 4  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_create_resources_no_mapped_blueprints_exist(
    mock_port_client: PortClient, mock_defaults: Defaults
) -> None:
    """
    Test case 2: No mapped blueprints exist in Port (they are in config but don't exist).
    Should create all blueprints, actions, scorecards, and pages from defaults.

    Flow:
    1. Get_blueprint is called for creation_stage default blueprints
       - These should NOT exist (raise exception) so blueprints_results = []
    2. _mapped_blueprints_exist calls get_blueprint for mapped blueprints
       - These should NOT exist (raise exception) so mapped_blueprints_exist = False
    3. Since both are False/empty, we create all resources
    """
    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "config": {
            "resources": [
                {
                    "port": {
                        "entity": {
                            "mappings": {
                                "blueprint": "blueprint1",
                            }
                        }
                    }
                },
                {
                    "port": {
                        "entity": {
                            "mappings": {
                                "blueprint": "blueprint2",
                            }
                        }
                    }
                },
            ]
        }
    }

    # Mock get_blueprint to always raise exception (blueprints don't exist)
    # This simulates that no blueprints exist in Port
    async def get_blueprint_side_effect(
        identifier: str, should_log: bool = True
    ) -> Blueprint:
        raise Exception(f"Blueprint {identifier} not found")

    mock_port_client.get_blueprint.side_effect = get_blueprint_side_effect  # type: ignore[attr-defined]

    # Mock create_blueprint to return created blueprint
    async def create_blueprint_side_effect(
        blueprint: dict[str, Any], user_agent_type: UserAgentType | None = None
    ) -> dict[str, Any]:
        return {"identifier": blueprint["identifier"], **blueprint}

    mock_port_client.create_blueprint.side_effect = create_blueprint_side_effect  # type: ignore[attr-defined]

    # Execute
    await _create_resources(
        mock_port_client, mock_defaults, has_provision_feature_flag=False
    )

    # Assert
    assert mock_port_client.create_blueprint.call_count == 2  # type: ignore[attr-defined]
    assert mock_port_client.patch_blueprint.call_count >= 2  # type: ignore[attr-defined]
    assert mock_port_client.create_action.call_count == 2  # type: ignore[attr-defined]
    assert mock_port_client.create_scorecard.call_count == 1  # type: ignore[attr-defined]
    assert mock_port_client.create_page.call_count == 1  # type: ignore[attr-defined]
