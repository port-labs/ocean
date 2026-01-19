from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import APIRouter, FastAPI
import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.types import UserAgentType
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.defaults.common import Defaults
from port_ocean.core.defaults.initialization.empty_setup import EmptySetup
from port_ocean.core.defaults.initialization.initialize import _initialize_defaults
from port_ocean.core.defaults.initialization.ocean_origin_setup import OceanOriginSetup
from port_ocean.core.defaults.initialization.port_origin_setup import PortOriginSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import Blueprint, CreatePortResourcesOrigin
from port_ocean.ocean import Ocean


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


def _mock_integration_config(
    create_port_resources_origin: CreatePortResourcesOrigin | None = None,
    initialize_port_resources: bool = True,
) -> IntegrationConfiguration:
    """Create a mock IntegrationConfiguration."""
    config = MagicMock(spec=IntegrationConfiguration)
    config.initialize_port_resources = initialize_port_resources
    config.create_port_resources_origin = create_port_resources_origin
    config.resources_path = ".port/resources"
    config.integration = MagicMock()
    config.integration.type = "test-integration"
    config.event_listener = MagicMock()
    config.event_listener.get_changelog_destination_details = MagicMock(return_value={})
    config.actions_processor = MagicMock()
    config.actions_processor.enabled = False
    return config


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
    mock_client.patch_integration = AsyncMock()
    mock_client.create_integration = AsyncMock()
    mock_client.poll_integration_until_default_provisioning_is_complete = AsyncMock()
    mock_client.integration_version = "1.0.0"
    return mock_client


@pytest.fixture
def mock_ocean(mock_port_client: PortClient) -> Ocean:
    ocean_mock = MagicMock(spec=Ocean)
    ocean_mock.config = MagicMock()
    ocean_mock.port_client = mock_port_client
    ocean_mock.integration_router = APIRouter()
    ocean_mock.fast_api_app = FastAPI()
    return ocean_mock


@pytest.fixture(autouse=True)
def mock_ocean_context(
    monkeypatch: pytest.MonkeyPatch, mock_ocean: Ocean
) -> PortOceanContext:
    mock_ocean_context = PortOceanContext(mock_ocean)
    mock_ocean_context._app = mock_ocean
    monkeypatch.setattr(
        "port_ocean.core.defaults.initialization.initialization_factory.ocean",
        mock_ocean_context,
    )
    monkeypatch.setattr(
        "port_ocean.core.defaults.initialization.initialize.ocean", mock_ocean_context
    )
    return mock_ocean_context


@pytest.fixture
def mock_port_app_config_class() -> type[PortAppConfig]:
    """Create a mock PortAppConfig class."""
    return PortAppConfig


@pytest.mark.asyncio
async def test_ocean_origin_setup_all_mapped_blueprints_exist(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_port_app_config_class: type[PortAppConfig],
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

    with patch(
        "port_ocean.core.defaults.initialization.ocean_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(
            mock_port_app_config_class, _mock_integration_config()
        )

    # Assert: Should not create any blueprints, actions, scorecards, or pages
    mock_port_client.create_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.patch_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_action.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_scorecard.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_page.assert_not_called()  # type: ignore[attr-defined]
    assert mock_port_client.get_blueprint.call_count == 4  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ocean_origin_setup_no_mapped_blueprints_exist(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
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

    with patch(
        "port_ocean.core.defaults.initialization.ocean_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(
            mock_port_app_config_class, _mock_integration_config()
        )

    # Assert
    assert mock_port_client.create_blueprint.call_count == 2  # type: ignore[attr-defined]
    assert mock_port_client.patch_blueprint.call_count >= 2  # type: ignore[attr-defined]
    assert mock_port_client.create_action.call_count == 2  # type: ignore[attr-defined]
    assert mock_port_client.create_scorecard.call_count == 1  # type: ignore[attr-defined]
    assert mock_port_client.create_page.call_count == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ocean_origin_setup_resources_initialization_disabled(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test that OceanOriginSetup skips resource creation when initialize_port_resources is False."""
    mock_integration_config.initialize_port_resources = False

    with patch(
        "port_ocean.core.defaults.initialization.ocean_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        setup = OceanOriginSetup(
            port_client=mock_port_client,
            integration_config=mock_integration_config,
            config_class=mock_port_app_config_class,
        )
        await setup._setup()

    # Assert: Should not create any resources
    mock_port_client.create_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.patch_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_action.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_scorecard.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_page.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_empty_setup(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test that EmptySetup creates integration with empty mapping only."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Empty
    )
    mock_port_client.get_current_integration.return_value = {}  # type: ignore[attr-defined]

    setup = EmptySetup(
        port_client=mock_port_client,
        integration_config=mock_integration_config,
        config_class=mock_port_app_config_class,
    )

    await setup._setup()

    # Assert: Should not create any resources
    mock_port_client.create_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.patch_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_action.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_scorecard.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_page.assert_not_called()  # type: ignore[attr-defined]

    # Assert: Should have empty mapping
    assert setup._default_mapping == PortAppConfig(resources=[])
    assert setup._port_resources_origin == CreatePortResourcesOrigin.Empty


@pytest.mark.asyncio
async def test_port_origin_setup(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test that PortOriginSetup polls for provisioned defaults."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Port
    )
    # Return an integration that exists (non-empty dict)
    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {},
        "installationAppType": "test-integration",
        "version": "1.0.0",
        "actionsProcessingEnabled": False,
    }
    mock_port_client.poll_integration_until_default_provisioning_is_complete.return_value = {  # type: ignore[attr-defined]
        "integration": {"config": {"resources": []}}
    }

    setup = PortOriginSetup(
        port_client=mock_port_client,
        integration_config=mock_integration_config,
        config_class=mock_port_app_config_class,
    )

    await setup._setup()

    # Assert: Should poll for provisioning
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_called_once()  # type: ignore[attr-defined]

    # Assert: Should not create resources directly
    mock_port_client.create_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.patch_blueprint.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_action.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_scorecard.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_page.assert_not_called()  # type: ignore[attr-defined]

    # Assert: Should have correct origin
    assert setup._port_resources_origin == CreatePortResourcesOrigin.Port
    assert setup._is_port_provisioning_enabled is True
