from typing import Any
from httpx import Response
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.clients.port.client import PortClient
from port_ocean.context import ocean
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.entities_state_applier.port.applier import (
    HttpEntitiesStateApplier,
)
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.integrations.mixins.live_events import LiveEventsMixin
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.ocean import Ocean


@pytest.fixture
def mock_context(mock_ocean: Ocean) -> PortOceanContext:
    context = PortOceanContext(mock_ocean)
    ocean._app = context.app
    return context


@pytest.fixture
def mock_entity_processor(mock_context: PortOceanContext) -> JQEntityProcessor:
    return JQEntityProcessor(mock_context)


@pytest.fixture
def mock_entities_state_applier(
    mock_context: PortOceanContext,
) -> HttpEntitiesStateApplier:
    return HttpEntitiesStateApplier(mock_context)


@pytest.fixture
def mock_port_app_config() -> PortAppConfig:
    return PortAppConfig(
        enable_merge_entity=True,
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        resources=[
            ResourceConfig(
                kind="project",
                selector=Selector(query="true"),
                port=PortResourceConfig(
                    entity=MappingsConfig(
                        mappings=EntityMapping(
                            identifier=".id | tostring",
                            title=".name",
                            blueprint='"service"',
                            properties={"url": ".web_url"},
                            relations={},
                        )
                    )
                ),
            )
        ],
    )


@pytest.fixture
def mock_port_app_config_handler(mock_port_app_config: PortAppConfig) -> MagicMock:
    handler = MagicMock()
    handler.get_port_app_config = AsyncMock(return_value=mock_port_app_config)
    return handler


@pytest.fixture
def mock_port_client(mock_http_client: MagicMock) -> PortClient:
    mock_port_client = PortClient(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )
    mock_port_client.auth = AsyncMock()
    mock_port_client.auth.headers = AsyncMock(
        return_value={
            "Authorization": "test",
            "User-Agent": "test",
        }
    )

    mock_port_client.search_entities = AsyncMock(return_value=[])  # type: ignore
    mock_port_client.client = mock_http_client
    return mock_port_client


@pytest.fixture
def mock_ocean(mock_port_client: PortClient) -> Ocean:
    with patch("port_ocean.ocean.Ocean.__init__", return_value=None):
        ocean_mock = Ocean(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        ocean_mock.config = MagicMock()
        ocean_mock.config.port = MagicMock()
        ocean_mock.config.port.port_app_config_cache_ttl = 60
        ocean_mock.port_client = mock_port_client

        return ocean_mock


@pytest.fixture
def mock_live_events_mixin(
    mock_entity_processor: JQEntityProcessor,
    mock_entities_state_applier: HttpEntitiesStateApplier,
    mock_port_app_config_handler: MagicMock,
) -> LiveEventsMixin:
    mixin = LiveEventsMixin()
    mixin._entity_processor = mock_entity_processor
    mixin._entities_state_applier = mock_entities_state_applier
    mixin._port_app_config_handler = mock_port_app_config_handler
    return mixin


@pytest.fixture
def mock_http_client() -> MagicMock:
    mock_http_client = MagicMock()
    mock_upserted_entities = []

    async def post(url: str, *args: Any, **kwargs: Any) -> Response:
        entity = kwargs.get("json", {})
        if entity.get("properties", {}).get("mock_is_to_fail", {}):
            return Response(
                404, headers=MagicMock(), json={"ok": False, "error": "not_found"}
            )

        mock_upserted_entities.append(
            f"{entity.get('identifier')}-{entity.get('blueprint')}"
        )
        return Response(
            200,
            json={
                "entity": {
                    "identifier": entity.get("identifier"),
                    "blueprint": entity.get("blueprint"),
                }
            },
        )

    mock_http_client.post = AsyncMock(side_effect=post)
    return mock_http_client


async def test_get_live_event_resources(
    mock_live_events_mixin: LiveEventsMixin, mock_port_app_config: PortAppConfig
):
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.return_value = (
        mock_port_app_config
    )

    result = await mock_live_events_mixin._get_live_event_resources("project")

    assert len(result) == 1
    assert result[0].kind == "project"  # Updated to match the actual config
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.assert_called_once_with(
        use_cache=False
    )


# async def test_get_entity_deletion_threshold(self, mixin):
#     # Arrange
#     mock_config = MagicMock()
#     mock_config.entity_deletion_threshold = 0.5
#     mixin.port_app_config_handler.get_port_app_config.return_value = mock_config

#     # Act
#     result = await mixin._get_entity_deletion_threshold()

#     # Assert
#     assert result == 0.5
#     mixin.port_app_config_handler.get_port_app_config.assert_called_once_with(use_cache=True)

# async def test_calculate_raw(self, mixin):
#     # Arrange
#     resource_config = ResourceConfig(kind="test_kind")
#     raw_data = [{"key": "value"}]
#     input_data = [(resource_config, raw_data)]

#     expected_result = CalculationResult(
#         entity_selector_diff=EntitySelectorDiff(passed=[], failed=[]),
#         raw_data_examples=[]
#     )
#     mixin.entity_processor.parse_items.return_value = expected_result

#     # Act
#     result = await mixin._calculate_raw(input_data)

#     # Assert
#     assert result == [expected_result]
#     mixin.entity_processor.parse_items.assert_called_once_with(
#         resource_config, raw_data, False, 0
#     )

# @patch('port_ocean.context.ocean')
# async def test_on_live_event(self, mock_ocean, mixin):
#     # Arrange
#     kind = "test_kind"
#     event_data = {"key": "value"}
#     resource_config = ResourceConfig(kind=kind)

#     mixin._get_live_event_resources.return_value = [resource_config]
#     mixin._get_entity_deletion_threshold.return_value = 0.5

#     calculation_result = CalculationResult(
#         entity_selector_diff=EntitySelectorDiff(passed=[{"id": "1"}], failed=[]),
#         raw_data_examples=[]
#     )
#     mixin._calculate_raw.return_value = [calculation_result]

#     modified_objects = [{"id": "1", "modified": True}]
#     mixin.entities_state_applier.upsert.return_value = modified_objects

#     entities_at_port = [{"id": "2"}]
#     mock_ocean.port_client.search_entities.return_value = entities_at_port

#     # Act
#     await mixin.on_live_event(kind, event_data)

#     # Assert
#     mixin._get_live_event_resources.assert_called_once_with(kind)
#     mixin._calculate_raw.assert_called_once_with([(resource_config, event_data)])
#     mixin.entities_state_applier.upsert.assert_called_once_with(
#         [{"id": "1"}], UserAgentType.exporter
#     )
#     mock_ocean.port_client.search_entities.assert_called_once_with(UserAgentType.exporter)
#     mixin.entities_state_applier.delete_diff.assert_called_once_with(
#         {"before": entities_at_port, "after": modified_objects},
#         UserAgentType.exporter,
#         0.5
#     )

# async def test_on_live_event_no_resources(self, mixin):
# Arrange
# kind = "test_kind"
# event_data = {"key": "value"}
# mixin._get_live_event_resources.return_value = []

# # Act
# await mixin.on_live_event(kind, event_data)

# # Assert
# mixin._get_live_event_resources.assert_called_once_with(kind)
# mixin._calculate_raw.assert_not_called()
# mixin.entities_state_applier.upsert.assert_not_called()
