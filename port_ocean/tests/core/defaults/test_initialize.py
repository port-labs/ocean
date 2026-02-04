from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import APIRouter, FastAPI
import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.types import UserAgentType
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.defaults.common import Defaults
from port_ocean.core.defaults.initialization.initialize import _initialize_defaults
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.models import (
    Blueprint,
    CreatePortResourcesOrigin,
    IntegrationFeatureFlag,
)
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


@pytest.fixture
def mock_integration_config() -> IntegrationConfiguration:
    """Create a mock IntegrationConfiguration."""
    config = MagicMock(spec=IntegrationConfiguration)
    config.initialize_port_resources = True
    config.create_port_resources_origin = None
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
    mock_client.is_integration_provision_enabled = AsyncMock(return_value=True)
    mock_client.get_organization_feature_flags = AsyncMock(
        return_value=[IntegrationFeatureFlag.USE_PROVISIONED_DEFAULTS]
    )
    mock_client.integration_version = "1.0.0"
    return mock_client


@pytest.fixture
def mock_ocean(
    mock_integration_config: IntegrationConfiguration, mock_port_client: PortClient
) -> Ocean:
    ocean_mock = MagicMock(spec=Ocean)
    ocean_mock.config = MagicMock()
    ocean_mock.port_client = mock_port_client
    ocean_mock.integration = MagicMock(spec=BaseIntegration)
    ocean_mock.integration.config = mock_integration_config
    ocean_mock.integration_router = APIRouter()
    ocean_mock.fast_api_app = FastAPI()
    ocean_mock.metrics = MagicMock()
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
async def test_default_origin_setup_all_mapped_blueprints_exist(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
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
    mock_integration_config.initialize_port_resources = True
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Default
    )
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
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

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
    mock_integration_config.initialize_port_resources = True
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Default
    )
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
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert
    assert mock_port_client.create_blueprint.call_count == 2  # type: ignore[attr-defined]
    assert mock_port_client.patch_blueprint.call_count >= 2  # type: ignore[attr-defined]
    assert mock_port_client.create_action.call_count == 2  # type: ignore[attr-defined]
    assert mock_port_client.create_scorecard.call_count == 1  # type: ignore[attr-defined]
    assert mock_port_client.create_page.call_count == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_default_origin_setup_resources_initialization_disabled(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test that DefaultOriginSetup skips resource creation when initialize_port_resources is False."""
    mock_integration_config.initialize_port_resources = False
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Default
    )
    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "config": {"resources": []}
    }

    with patch(
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

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

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should create integration with empty port_app_config
    mock_port_client.create_integration.assert_called_once()  # type: ignore[attr-defined]
    call_args = mock_port_client.create_integration.call_args  # type: ignore[attr-defined]
    assert call_args.kwargs["port_app_config"] == PortAppConfig(resources=[])
    assert (
        call_args.kwargs["create_port_resources_origin"]
        == CreatePortResourcesOrigin.Empty
    )


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

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should poll for provisioning
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_none_origin_with_provision_enabled(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test that when create_port_resources_origin is None and both feature flag and integration support are enabled, it uses Port."""
    mock_integration_config.create_port_resources_origin = None

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

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should use Port origin setup (poll for provisioning)
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_none_origin_with_feature_flag_disabled(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test that when create_port_resources_origin is None and feature flag is disabled, it uses Ocean."""
    mock_integration_config.create_port_resources_origin = None
    mock_integration_config.initialize_port_resources = True

    # Mock integration support enabled but feature flag disabled
    mock_port_client.is_integration_provision_enabled.return_value = True  # type: ignore[attr-defined]
    mock_port_client.get_organization_feature_flags.return_value = []  # type: ignore[attr-defined]

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
            ]
        }
    }

    # Mock get_blueprint to always raise exception (blueprints don't exist)
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
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should use Default origin setup (create resources)
    mock_port_client.is_integration_provision_enabled.assert_called_once_with(  # type: ignore[attr-defined]
        "test-integration"
    )
    mock_port_client.get_organization_feature_flags.assert_called_once()  # type: ignore[attr-defined]
    mock_port_client.create_blueprint.assert_called()  # type: ignore[attr-defined]
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_none_origin_with_integration_support_disabled(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test that when create_port_resources_origin is None and integration support is disabled, it uses Ocean."""
    mock_integration_config.create_port_resources_origin = None
    mock_integration_config.initialize_port_resources = True

    # Mock feature flag enabled but integration support disabled
    mock_port_client.is_integration_provision_enabled.return_value = False  # type: ignore[attr-defined]
    mock_port_client.get_organization_feature_flags.return_value = [  # type: ignore[attr-defined]
        IntegrationFeatureFlag.USE_PROVISIONED_DEFAULTS
    ]

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
            ]
        }
    }

    # Mock get_blueprint to always raise exception (blueprints don't exist)
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
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should use Default origin setup (create resources, not integration)
    mock_port_client.create_integration.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_blueprint.assert_called()  # type: ignore[attr-defined]
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_empty_setup_integration_not_exists(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test EmptySetup when integration doesn't exist - should create it with empty mapping."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Empty
    )
    mock_port_client.get_current_integration.return_value = {}  # type: ignore[attr-defined]
    mock_port_client.create_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {"resources": []},
    }

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should create integration with empty port_app_config
    mock_port_client.create_integration.assert_called_once()  # type: ignore[attr-defined]
    call_args = mock_port_client.create_integration.call_args  # type: ignore[attr-defined]
    assert call_args.kwargs["port_app_config"] == PortAppConfig(resources=[])
    assert (
        call_args.kwargs["create_port_resources_origin"]
        == CreatePortResourcesOrigin.Empty
    )


@pytest.mark.asyncio
async def test_empty_setup_integration_exists(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test EmptySetup when integration exists - should continue without creating."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Empty
    )
    # Make sure all fields match to avoid patch_integration call
    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {"resources": []},
        "installationAppType": "test-integration",
        "version": "1.0.0",
        "portCreateResourcesOrigin": CreatePortResourcesOrigin.Empty.value,
        "actionsProcessingEnabled": False,
        "changelogDestination": {},
    }

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should not create integration, just verify configuration
    mock_port_client.create_integration.assert_not_called()  # type: ignore[attr-defined]
    # patch_integration may be called if config differs, which is expected behavior


@pytest.mark.asyncio
async def test_default_setup_integration_not_exists(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test DefaultOriginSetup when integration doesn't exist - should create it and create resources."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Default
    )
    mock_integration_config.initialize_port_resources = True
    mock_port_client.is_integration_provision_enabled.return_value = False  # type: ignore[attr-defined]
    mock_port_client.get_organization_feature_flags.return_value = []  # type: ignore[attr-defined]
    # First call returns empty (integration doesn't exist), subsequent calls return created integration
    call_count = 0

    async def get_current_integration_side_effect(
        *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {}  # Integration doesn't exist
        # After creation, return integration with resources containing mapped blueprint that doesn't exist
        return {
            "identifier": "test-integration",
            "config": {
                "resources": [
                    {
                        "port": {
                            "entity": {
                                "mappings": {
                                    "blueprint": "nonexistent-blueprint",
                                }
                            }
                        }
                    }
                ]
            },
        }

    mock_port_client.get_current_integration.side_effect = get_current_integration_side_effect  # type: ignore[attr-defined]
    mock_port_client.create_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {},
    }

    # Mock get_blueprint to always raise exception (blueprints don't exist)
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
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should create integration and then create resources
    mock_port_client.create_integration.assert_called_once()  # type: ignore[attr-defined]
    mock_port_client.create_blueprint.assert_called()  # type: ignore[attr-defined]
    mock_port_client.create_action.assert_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_default_setup_integration_exists(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test DefaultOriginSetup when integration exists - should continue and create resources if needed."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Default
    )
    mock_integration_config.initialize_port_resources = True
    mock_port_client.is_integration_provision_enabled.return_value = False  # type: ignore[attr-defined]
    mock_port_client.get_organization_feature_flags.return_value = []  # type: ignore[attr-defined]
    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
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
            ]
        },
        "installationAppType": "test-integration",
        "version": "1.0.0",
        "actionsProcessingEnabled": False,
    }

    # Mock get_blueprint to always raise exception (blueprints don't exist)
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
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should not create integration, but should create resources
    mock_port_client.create_integration.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_blueprint.assert_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_port_setup_integration_not_exists(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test PortOriginSetup when integration doesn't exist - should create it and wait for provisioning."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Port
    )
    mock_port_client.get_current_integration.return_value = {}  # type: ignore[attr-defined]
    mock_port_client.create_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {},
    }
    mock_port_client.poll_integration_until_default_provisioning_is_complete.return_value = {  # type: ignore[attr-defined]
        "integration": {
            "config": {"resources": [{"port": {"entity": {"mappings": {}}}}]}
        }
    }

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should create integration with Port provisioning and wait for provisioning
    mock_port_client.create_integration.assert_called_once()  # type: ignore[attr-defined]
    call_args = mock_port_client.create_integration.call_args  # type: ignore[attr-defined]
    assert (
        call_args.kwargs["create_port_resources_origin"]
        == CreatePortResourcesOrigin.Port
    )
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_port_setup_integration_exists_config_falsy(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test PortOriginSetup when integration exists but config is falsy - should wait for provisioning."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Port
    )
    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {},  # Falsy config
        "portCreateResourcesOrigin": CreatePortResourcesOrigin.Port.value,
        "installationAppType": "test-integration",
        "version": "1.0.0",
        "actionsProcessingEnabled": False,
    }
    mock_port_client.poll_integration_until_default_provisioning_is_complete.return_value = {  # type: ignore[attr-defined]
        "integration": {
            "config": {"resources": [{"port": {"entity": {"mappings": {}}}}]}
        }
    }

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should not create integration, but should wait for provisioning
    mock_port_client.create_integration.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_port_setup_integration_exists_config_not_empty(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test PortOriginSetup when integration exists and config is not empty - should continue (poll returns immediately)."""
    mock_integration_config.create_port_resources_origin = (
        CreatePortResourcesOrigin.Port
    )
    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {"resources": [{"port": {"entity": {"mappings": {}}}}]},  # Not empty
        "installationAppType": "test-integration",
        "version": "1.0.0",
        "actionsProcessingEnabled": False,
    }
    # Poll should return immediately when config is not empty
    mock_port_client.poll_integration_until_default_provisioning_is_complete.return_value = {  # type: ignore[attr-defined]
        "integration": {
            "config": {"resources": [{"port": {"entity": {"mappings": {}}}}]}
        }
    }

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should not create integration, poll should be called but return immediately
    mock_port_client.create_integration.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_none_origin_provision_enabled_integration_not_exists(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test None origin with provision enabled when integration doesn't exist - should use Port and create it."""
    mock_integration_config.create_port_resources_origin = None

    mock_port_client.get_current_integration.return_value = {}  # type: ignore[attr-defined]
    mock_port_client.create_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {},
    }
    mock_port_client.poll_integration_until_default_provisioning_is_complete.return_value = {  # type: ignore[attr-defined]
        "integration": {
            "config": {"resources": [{"port": {"entity": {"mappings": {}}}}]}
        }
    }

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should use Port origin setup (create integration and wait for provisioning)
    mock_port_client.create_integration.assert_called_once()  # type: ignore[attr-defined]
    call_args = mock_port_client.create_integration.call_args  # type: ignore[attr-defined]
    assert (
        call_args.kwargs["create_port_resources_origin"]
        == CreatePortResourcesOrigin.Port
    )
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_none_origin_provision_enabled_integration_exists(
    mock_port_client: PortClient,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test None origin with provision enabled when integration exists - should use Port and continue."""
    mock_integration_config.create_port_resources_origin = None

    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {"resources": [{"port": {"entity": {"mappings": {}}}}]},
        "portCreateResourcesOrigin": CreatePortResourcesOrigin.Port.value,
        "installationAppType": "test-integration",
        "version": "1.0.0",
        "actionsProcessingEnabled": False,
    }
    mock_port_client.poll_integration_until_default_provisioning_is_complete.return_value = {  # type: ignore[attr-defined]
        "integration": {
            "config": {"resources": [{"port": {"entity": {"mappings": {}}}}]}
        }
    }

    await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should use Port origin setup (poll for provisioning)
    mock_port_client.create_integration.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_none_origin_provision_disabled_integration_not_exists(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test None origin with provision disabled when integration doesn't exist - should use Ocean and create it."""
    mock_integration_config.create_port_resources_origin = None
    mock_integration_config.initialize_port_resources = True

    # Mock provision disabled
    mock_port_client.is_integration_provision_enabled.return_value = False  # type: ignore[attr-defined]
    mock_port_client.get_organization_feature_flags.return_value = []  # type: ignore[attr-defined]

    # First call returns empty (integration doesn't exist), subsequent calls return created integration
    call_count = 0

    async def get_current_integration_side_effect(
        *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {}  # Integration doesn't exist
        # After creation, return integration with resources containing mapped blueprint that doesn't exist
        return {
            "identifier": "test-integration",
            "config": {
                "resources": [
                    {
                        "port": {
                            "entity": {
                                "mappings": {
                                    "blueprint": "nonexistent-blueprint",
                                }
                            }
                        }
                    }
                ]
            },
        }

    mock_port_client.get_current_integration.side_effect = get_current_integration_side_effect  # type: ignore[attr-defined]
    mock_port_client.create_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
        "config": {},
    }

    # Mock get_blueprint to always raise exception (blueprints don't exist)
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
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should use Ocean origin setup (create integration and resources)
    mock_port_client.create_integration.assert_called_once()  # type: ignore[attr-defined]
    call_args = mock_port_client.create_integration.call_args  # type: ignore[attr-defined]
    assert (
        call_args.kwargs["create_port_resources_origin"]
        == CreatePortResourcesOrigin.Default
    )
    mock_port_client.create_blueprint.assert_called()  # type: ignore[attr-defined]
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_none_origin_provision_disabled_integration_exists(
    mock_port_client: PortClient,
    mock_defaults: Defaults,
    mock_integration_config: IntegrationConfiguration,
    mock_port_app_config_class: type[PortAppConfig],
) -> None:
    """Test None origin with provision disabled when integration exists - should use Ocean and continue."""
    mock_integration_config.create_port_resources_origin = None
    mock_integration_config.initialize_port_resources = True

    # Mock provision disabled
    mock_port_client.is_integration_provision_enabled.return_value = False  # type: ignore[attr-defined]
    mock_port_client.get_organization_feature_flags.return_value = []  # type: ignore[attr-defined]

    mock_port_client.get_current_integration.return_value = {  # type: ignore[attr-defined]
        "identifier": "test-integration",
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
            ]
        },
        "portCreateResourcesOrigin": CreatePortResourcesOrigin.Port.value,
        "installationAppType": "test-integration",
        "version": "1.0.0",
        "actionsProcessingEnabled": False,
    }

    # Mock get_blueprint to always raise exception (blueprints don't exist)
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
        "port_ocean.core.defaults.initialization.default_origin_setup.get_port_integration_defaults",
        return_value=mock_defaults,
    ):
        await _initialize_defaults(mock_port_app_config_class, mock_integration_config)

    # Assert: Should use Ocean origin setup (create resources, not integration)
    mock_port_client.create_integration.assert_not_called()  # type: ignore[attr-defined]
    mock_port_client.create_blueprint.assert_called()  # type: ignore[attr-defined]
    mock_port_client.poll_integration_until_default_provisioning_is_complete.assert_not_called()  # type: ignore[attr-defined]
