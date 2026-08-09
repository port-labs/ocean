import pytest
from unittest.mock import MagicMock, patch
from pydantic.v1 import ValidationError
from typing import Any, Dict

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.base import BasePortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.context.event import EventType, event_context
from port_ocean.exceptions.api import EmptyPortAppConfigError


class MockPortAppConfig(BasePortAppConfig):
    mock_get_port_app_config: Any

    async def _get_port_app_config(self) -> Dict[str, Any]:
        return self.mock_get_port_app_config()


@pytest.fixture
def mock_context() -> PortOceanContext:
    context = MagicMock(spec=PortOceanContext)
    context.config.port.port_app_config_cache_ttl = 300  # 5 minutes
    return context


@pytest.fixture
def port_app_config_handler(mock_context: PortOceanContext) -> MockPortAppConfig:
    handler = MockPortAppConfig(mock_context)
    handler.mock_get_port_app_config = MagicMock()
    return handler


@pytest.mark.asyncio
async def test_get_port_app_config_success(
    port_app_config_handler: MockPortAppConfig,
) -> None:
    # Arrange
    valid_config = {
        "resources": [
            {
                "kind": "repository",
                "selector": {"query": "true"},
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".name",
                            "title": ".name",
                            "blueprint": '"service"',
                            "properties": {
                                "description": ".description",
                                "url": ".html_url",
                                "defaultBranch": ".default_branch",
                            },
                        }
                    }
                },
            }
        ]
    }
    port_app_config_handler.mock_get_port_app_config.return_value = valid_config

    # Act
    async with event_context(EventType.RESYNC, trigger_type="machine"):
        result = await port_app_config_handler.get_port_app_config()

    # Assert
    assert isinstance(result, PortAppConfig)
    assert result.resources[0].port.entity.mappings.title == ".name"
    assert result.resources[0].port.entity.mappings.identifier == ".name"
    assert result.resources[0].port.entity.mappings.blueprint == '"service"'
    assert (
        result.resources[0].port.entity.mappings.properties["description"]
        == ".description"
    )
    assert result.resources[0].port.entity.mappings.properties["url"] == ".html_url"
    assert (
        result.resources[0].port.entity.mappings.properties["defaultBranch"]
        == ".default_branch"
    )
    port_app_config_handler.mock_get_port_app_config.assert_called_once()


@pytest.mark.asyncio
async def test_get_port_app_config_get_entity_deletion_threshold_with_flag_defined(
    port_app_config_handler: MockPortAppConfig,
) -> None:
    # Arrange
    valid_config = {
        "entityDeletionThreshold": 0.1,
        "resources": [
            {
                "kind": "repository",
                "selector": {"query": "true"},
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".name",
                            "title": ".name",
                            "blueprint": '"service"',
                            "properties": {
                                "description": ".description",
                                "url": ".html_url",
                                "defaultBranch": ".default_branch",
                            },
                        }
                    }
                },
            }
        ],
    }
    port_app_config_handler.mock_get_port_app_config.return_value = valid_config

    # Act
    async with event_context(EventType.RESYNC, trigger_type="machine"):
        result = await port_app_config_handler.get_port_app_config()
        deletion_threshold = result.entity_deletion_threshold

    # Assert
    assert isinstance(result, PortAppConfig)
    assert deletion_threshold == 0.1
    port_app_config_handler.mock_get_port_app_config.assert_called_once()


@pytest.mark.asyncio
async def test_get_port_app_config_get_entity_deletion_threshold_with_flag_not_defined(
    port_app_config_handler: MockPortAppConfig,
) -> None:
    # Arrange
    valid_config = {
        "resources": [
            {
                "kind": "repository",
                "selector": {"query": "true"},
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".name",
                            "title": ".name",
                            "blueprint": '"service"',
                            "properties": {
                                "description": ".description",
                                "url": ".html_url",
                                "defaultBranch": ".default_branch",
                            },
                        }
                    }
                },
            }
        ]
    }
    port_app_config_handler.mock_get_port_app_config.return_value = valid_config

    # Act
    async with event_context(EventType.RESYNC, trigger_type="machine"):
        result = await port_app_config_handler.get_port_app_config()
        deletion_threshold = result.entity_deletion_threshold

    # Assert
    assert isinstance(result, PortAppConfig)
    assert deletion_threshold == 0.9
    port_app_config_handler.mock_get_port_app_config.assert_called_once()


@pytest.mark.asyncio
async def test_get_port_app_config_uses_cache(
    port_app_config_handler: MockPortAppConfig,
) -> None:
    # Arrange
    valid_config = {
        "resources": [
            {
                "kind": "repository",
                "selector": {"query": "true"},
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".name",
                            "title": ".name",
                            "blueprint": '"service"',
                            "properties": {
                                "description": ".description",
                                "url": ".html_url",
                                "defaultBranch": ".default_branch",
                            },
                        }
                    }
                },
            }
        ]
    }
    port_app_config_handler.mock_get_port_app_config.return_value = valid_config

    # Act
    async with event_context(EventType.RESYNC, trigger_type="machine"):
        result1 = await port_app_config_handler.get_port_app_config()
        result2 = await port_app_config_handler.get_port_app_config()

        # Assert
        assert result1 == result2
        port_app_config_handler.mock_get_port_app_config.assert_called_once()  # Called only once due to caching


@pytest.mark.asyncio
async def test_get_port_app_config_bypass_cache(
    port_app_config_handler: MockPortAppConfig,
) -> None:
    # Arrange
    valid_config = {
        "resources": [
            {
                "kind": "repository",
                "selector": {"query": "true"},
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".name",
                            "title": ".name",
                            "blueprint": '"service"',
                            "properties": {
                                "description": ".description",
                                "url": ".html_url",
                                "defaultBranch": ".default_branch",
                            },
                        }
                    }
                },
            }
        ]
    }
    port_app_config_handler.mock_get_port_app_config.return_value = valid_config

    # Act
    async with event_context(EventType.RESYNC, trigger_type="machine"):
        result1 = await port_app_config_handler.get_port_app_config()
        result2 = await port_app_config_handler.get_port_app_config(use_cache=False)

        # Assert
        assert result1 == result2
        assert (
            port_app_config_handler.mock_get_port_app_config.call_count == 2
        )  # Called twice due to cache bypass


@pytest.mark.asyncio
async def test_get_port_app_config_validation_error(
    port_app_config_handler: MockPortAppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    invalid_config = {"invalid_field": "invalid_value"}
    port_app_config_handler.mock_get_port_app_config.return_value = invalid_config

    def mock_parse_obj(*args: Any, **kwargs: Any) -> None:
        raise ValidationError(errors=[], model=PortAppConfig)

    monkeypatch.setattr(
        port_app_config_handler.CONFIG_CLASS, "parse_obj", mock_parse_obj
    )

    # Act & Assert
    with pytest.raises(ValidationError):
        async with event_context(EventType.RESYNC, trigger_type="machine"):
            await port_app_config_handler.get_port_app_config()


@pytest.mark.asyncio
async def test_get_port_app_config_fetch_error(
    port_app_config_handler: MockPortAppConfig,
) -> None:
    # Arrange
    port_app_config_handler.mock_get_port_app_config.side_effect = (
        EmptyPortAppConfigError("Port app config is empty")
    )

    # Act & Assert
    async with event_context(EventType.RESYNC, trigger_type="machine"):
        with pytest.raises(EmptyPortAppConfigError, match="Port app config is empty"):
            await port_app_config_handler.get_port_app_config()


def test_to_dsp_lifecycle_mapping_wraps_mappings_in_array() -> None:
    config = PortAppConfig(
        delete_dependent_entities=False,
        create_missing_related_entities=False,
        entity_deletion_threshold=1,
        resources=[
            ResourceConfig(
                kind="repository",
                selector=Selector(query="true"),
                port=PortResourceConfig(
                    entity=MappingsConfig(
                        mappings=EntityMapping(
                            identifier=".name",
                            title=".name",
                            blueprint='"service"',
                            properties={"url": ".html_url"},
                        )
                    )
                ),
            )
        ],
    )

    mapping = config.to_dsp_lifecycle_mapping()

    assert mapping["deleteDependentEntities"] is False
    assert mapping["createMissingRelatedEntities"] is False
    assert mapping["entityDeletionThreshold"] == 1
    resource = mapping["resources"][0]
    assert resource["kind"] == "repository"
    assert resource["selector"]["query"] == "true"
    mappings = resource["port"]["entity"]["mappings"]
    assert isinstance(mappings, list)
    assert len(mappings) == 1
    assert mappings[0]["identifier"] == ".name"
    assert mappings[0]["blueprint"] == '"service"'
    assert mappings[0]["properties"]["url"] == ".html_url"


def test_to_dsp_lifecycle_mapping_leaves_array_mappings_unchanged() -> None:
    mapping = {
        "resources": [
            {
                "kind": "repository",
                "port": {
                    "entity": {
                        "mappings": [
                            {
                                "identifier": ".name",
                                "blueprint": '"service"',
                            }
                        ]
                    }
                },
            }
        ]
    }
    config = PortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "repository",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".name",
                                "blueprint": '"service"',
                            }
                        }
                    },
                }
            ]
        }
    )

    with patch.object(PortAppConfig, "to_request", return_value=mapping):
        result = config.to_dsp_lifecycle_mapping()

    assert result["resources"][0]["port"]["entity"]["mappings"] == [
        {"identifier": ".name", "blueprint": '"service"'}
    ]
