from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.clients.port.client import PortClient
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
    Test case 1: All mapped blueprints exist in the integration config.
    Should skip creation of all resources.

    Flow:
    1. First, get_blueprint is called for creation_stage blueprints (blueprint1, blueprint2)
       - These should NOT exist (raise exception) so blueprints_results = []
    2. Then _mapped_blueprints_exist calls get_blueprint for mapped blueprints
       - These SHOULD exist (return Blueprint) so mapped_blueprints_exist = True
    3. Since mapped_blueprints_exist is True, we skip creation
    """
    # Setup: Mock get_current_integration to return integration with resources
    # containing blueprints in mappings (lines 139-142)
    mock_port_client.get_current_integration.return_value = {
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

    # Track call order: first 2 calls are for creation_stage, next 2 are for mapped blueprints
    call_count = 0

    async def get_blueprint_side_effect(identifier: str, should_log: bool = True):
        nonlocal call_count
        call_count += 1

        # First 2 calls are for creation_stage blueprints (lines 182-188)
        # These should NOT exist to make blueprints_results = []
        if call_count <= 2:
            raise Exception(f"Blueprint {identifier} not found")

        # Next 2 calls are for mapped blueprints (lines 156-162)
        # These SHOULD exist to make mapped_blueprints_exist = True
        return Blueprint(
            identifier=identifier,
            title=f"Blueprint {identifier}",
            team=None,
            properties_schema={"type": "object", "properties": {}},
            relations={},
        )

    mock_port_client.get_blueprint.side_effect = get_blueprint_side_effect

    # Execute
    await _create_resources(
        mock_port_client, mock_defaults, has_provision_feature_flag=False
    )

    # Assert: Should not create any blueprints, actions, scorecards, or pages
    mock_port_client.create_blueprint.assert_not_called()
    mock_port_client.patch_blueprint.assert_not_called()
    mock_port_client.create_action.assert_not_called()
    mock_port_client.create_scorecard.assert_not_called()
    mock_port_client.create_page.assert_not_called()

    # Verify get_blueprint was called 4 times total (2 for creation_stage + 2 for mapped)
    assert mock_port_client.get_blueprint.call_count == 4


@pytest.mark.asyncio
async def test_create_resources_no_mapped_blueprints_exist(
    mock_port_client: PortClient, mock_defaults: Defaults
) -> None:
    """
    Test case 2: No mapped blueprints exist in Port (they are in config but don't exist).
    Should create all blueprints, actions, scorecards, and pages from defaults.

    Flow:
    1. First, get_blueprint is called for creation_stage blueprints (blueprint1, blueprint2)
       - These should NOT exist (raise exception) so blueprints_results = []
    2. Then _mapped_blueprints_exist calls get_blueprint for mapped blueprints
       - These should NOT exist (raise exception) so mapped_blueprints_exist = False
    3. Since both are False/empty, we create all resources
    """
    # Setup: Mock get_current_integration to return integration with resources
    # containing blueprints in mappings, but these blueprints don't exist in Port
    mock_port_client.get_current_integration.return_value = {
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
    async def get_blueprint_side_effect(identifier: str, should_log: bool = True):
        raise Exception(f"Blueprint {identifier} not found")

    mock_port_client.get_blueprint.side_effect = get_blueprint_side_effect

    # Mock create_blueprint to return created blueprint
    def create_blueprint_side_effect(blueprint: dict, user_agent_type=None):
        return {"identifier": blueprint["identifier"], **blueprint}

    mock_port_client.create_blueprint.side_effect = create_blueprint_side_effect

    # Execute
    await _create_resources(
        mock_port_client, mock_defaults, has_provision_feature_flag=False
    )

    # Assert: Should create all blueprints from creation_stage (2 blueprints)
    assert mock_port_client.create_blueprint.call_count == 2

    # Assert: Should patch blueprints (2 patch stages: with_relations and full_blueprint)
    assert mock_port_client.patch_blueprint.call_count >= 2

    # Assert: Should create all actions (2 actions)
    assert mock_port_client.create_action.call_count == 2

    # Assert: Should create scorecards (1 scorecard)
    assert mock_port_client.create_scorecard.call_count == 1

    # Assert: Should create pages (1 page)
    assert mock_port_client.create_page.call_count == 1


@pytest.mark.asyncio
async def test_create_resources_some_mapped_blueprints_exist(
    mock_port_client: PortClient, mock_defaults: Defaults
) -> None:
    """
    Test case 3: Some (but not all) mapped blueprints exist.
    Should create all blueprints from defaults since not all mapped blueprints exist.

    Flow:
    1. First, get_blueprint is called for creation_stage blueprints (blueprint1, blueprint2)
       - These should NOT exist (raise exception) so blueprints_results = []
    2. Then _mapped_blueprints_exist calls get_blueprint for mapped blueprints
       - blueprint1 exists, blueprint2 doesn't exist
       - Since not all exist, mapped_blueprints_exist = False
    3. Since both are False/empty, we create all resources
    """
    # Setup: Mock get_current_integration to return integration with resources
    # containing both blueprints in mappings
    mock_port_client.get_current_integration.return_value = {
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

    # Track call order: first 2 calls are for creation_stage, next 2 are for mapped blueprints
    call_count = 0

    async def get_blueprint_side_effect(identifier: str, should_log: bool = True):
        nonlocal call_count
        call_count += 1

        # First 2 calls are for creation_stage blueprints (lines 182-188)
        # These should NOT exist to make blueprints_results = []
        if call_count <= 2:
            raise Exception(f"Blueprint {identifier} not found")

        # Next 2 calls are for mapped blueprints (lines 156-162)
        # blueprint1 exists, blueprint2 doesn't exist
        if identifier == "blueprint1":
            return Blueprint(
                identifier=identifier,
                title=f"Blueprint {identifier}",
                team=None,
                properties_schema={"type": "object", "properties": {}},
                relations={},
            )
        else:
            raise Exception(f"Blueprint {identifier} not found")

    mock_port_client.get_blueprint.side_effect = get_blueprint_side_effect

    # Mock create_blueprint to return created blueprint
    def create_blueprint_side_effect(blueprint: dict, user_agent_type=None):
        return {"identifier": blueprint["identifier"], **blueprint}

    mock_port_client.create_blueprint.side_effect = create_blueprint_side_effect

    # Execute
    await _create_resources(
        mock_port_client, mock_defaults, has_provision_feature_flag=False
    )

    # Assert: Should create all blueprints from creation_stage (2 blueprints)
    # because _mapped_blueprints_exist returns False (not all mapped blueprints exist)
    assert mock_port_client.create_blueprint.call_count == 2

    # Assert: Should patch blueprints
    assert mock_port_client.patch_blueprint.call_count >= 2

    # Assert: Should create all actions
    assert mock_port_client.create_action.call_count == 2

    # Assert: Should create scorecards
    assert mock_port_client.create_scorecard.call_count == 1

    # Assert: Should create pages
    assert mock_port_client.create_page.call_count == 1
