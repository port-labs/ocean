from typing import Any
from httpx import Response
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.clients.port.client import PortClient
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
from port_ocean.core.models import Entity
from port_ocean.ocean import Ocean


@pytest.fixture
def mock_context(monkeypatch: Any) -> PortOceanContext:
    mock_context = AsyncMock()
    monkeypatch.setattr(PortOceanContext, "app", mock_context)
    return mock_context


@pytest.fixture
def mock_entity_processor(mock_context: PortOceanContext) -> JQEntityProcessor:
    return JQEntityProcessor(mock_context)


@pytest.fixture
def mock_entities_state_applier(
    mock_context: PortOceanContext,
) -> HttpEntitiesStateApplier:
    return HttpEntitiesStateApplier(mock_context)


@pytest.fixture
def mock_repository_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="repository",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    title=".name",
                    blueprint='"service"',
                    properties={
                        "url": ".links.html.href",
                        "readme": "file://README.md",
                        "defaultBranch": ".main_branch",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def mock_port_app_config_with_repository_resource(
    mock_repository_resource_config: ResourceConfig,
) -> PortAppConfig:
    return PortAppConfig(
        enable_merge_entity=True,
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        resources=[mock_repository_resource_config],
        entity_deletion_threshold=0.5,
    )


@pytest.fixture
def mock_port_app_config_handler(
    mock_port_app_config_with_repository_resource: PortAppConfig,
) -> MagicMock:
    handler = MagicMock()
    handler.get_port_app_config = AsyncMock(
        return_value=mock_port_app_config_with_repository_resource
    )
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


@pytest.mark.asyncio
async def test_getLiveEventResources_mappingHasTheResource_returnsTheResource(
    mock_live_events_mixin: LiveEventsMixin,
    mock_port_app_config_with_repository_resource: PortAppConfig,
) -> None:
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.return_value = (
        mock_port_app_config_with_repository_resource
    )

    result = await mock_live_events_mixin._get_live_event_resources("repository")

    assert len(result) == 1
    assert result[0].kind == "repository"
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.assert_called_once_with(
        use_cache=False
    )


@pytest.mark.asyncio
async def test_getLiveEventResources_mappingDoesNotHaveTheResource_returnsEmptyList(
    mock_live_events_mixin: LiveEventsMixin,
    mock_port_app_config_with_repository_resource: PortAppConfig,
) -> None:
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.return_value = (
        mock_port_app_config_with_repository_resource
    )

    result = await mock_live_events_mixin._get_live_event_resources("project")

    assert len(result) == 0
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.assert_called_once_with(
        use_cache=False
    )


@pytest.mark.asyncio
async def test_getLiveEventResources_exceptionWhenGettingPortAppConfig_raisesException(
    mock_live_events_mixin: LiveEventsMixin,
) -> None:
    mock_error = Exception("Test error")
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.side_effect = (
        mock_error
    )

    with pytest.raises(Exception) as exc_info:
        await mock_live_events_mixin._get_live_event_resources("repository")

    assert str(exc_info.value) == "Test error"


@pytest.mark.asyncio
async def test_getEntityDeletionThreshold_returnsTheThreshold(
    mock_live_events_mixin: LiveEventsMixin,
    mock_port_app_config_with_repository_resource: PortAppConfig,
) -> None:
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.return_value = (
        mock_port_app_config_with_repository_resource
    )

    result = await mock_live_events_mixin._get_entity_deletion_threshold()

    assert result == 0.5
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.assert_called_once_with(
        use_cache=True
    )


@pytest.mark.asyncio
async def test_calculateRaw_oneRawDataMatchesTheResourceConfig_returnsTheResult(
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    sample_data = {
        "name": "my-example-repo",
        "links": {"html": {"href": "https://example.com/my-example-repo"}},
        "main_branch": "main",
    }
    input_data = [(mock_repository_resource_config, [sample_data])]
    expected_entity = Entity(
        identifier="my-example-repo",
        blueprint="service",
        title="my-example-repo",
        team=[],
        properties={
            "url": "https://example.com/my-example-repo",
            "readme": None,
            "defaultBranch": "main",
        },
        relations={},
    )

    result = await mock_live_events_mixin._calculate_raw(input_data)

    assert result[0].entity_selector_diff.passed[0] == expected_entity


@pytest.mark.asyncio
async def test_calculateRaw_multipleRawDataMatchesTheResourceConfig_returnsAllResults(
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    sample_data = [
        {
            "name": "repo-one",
            "links": {"html": {"href": "https://example.com/repo-one"}},
            "main_branch": "main",
        },
        {
            "name": "repo-two",
            "links": {"html": {"href": "https://example.com/repo-two"}},
            "main_branch": "develop",
        },
        {
            "name": "repo-three",
            "links": {"html": {"href": "https://example.com/repo-three"}},
            "main_branch": "master",
        },
    ]
    input_data = [(mock_repository_resource_config, sample_data)]

    expected_entities = [
        Entity(
            identifier="repo-one",
            blueprint="service",
            title="repo-one",
            team=[],
            properties={
                "url": "https://example.com/repo-one",
                "readme": None,
                "defaultBranch": "main",
            },
            relations={},
        ),
        Entity(
            identifier="repo-two",
            blueprint="service",
            title="repo-two",
            team=[],
            properties={
                "url": "https://example.com/repo-two",
                "readme": None,
                "defaultBranch": "develop",
            },
            relations={},
        ),
        Entity(
            identifier="repo-three",
            blueprint="service",
            title="repo-three",
            team=[],
            properties={
                "url": "https://example.com/repo-three",
                "readme": None,
                "defaultBranch": "master",
            },
            relations={},
        ),
    ]

    result = await mock_live_events_mixin._calculate_raw(input_data)

    assert len(result[0].entity_selector_diff.passed) == 3
    for expected, actual in zip(
        expected_entities, result[0].entity_selector_diff.passed
    ):
        assert expected == actual


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
