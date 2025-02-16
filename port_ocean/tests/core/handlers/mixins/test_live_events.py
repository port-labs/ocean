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
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventData
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
from port_ocean.core.ocean_types import CalculationResult, EntitySelectorDiff
from port_ocean.ocean import Ocean
from port_ocean.context.event import event_context

entity = Entity(
    identifier="repo-one",
    blueprint="service",
    title="repo-one",
    team=[],
    properties={
        "url": "https://example.com/repo-one",
        "defaultBranch": "main",
    },
    relations={},
)

expected_entities = [
    Entity(
        identifier="repo-one",
        blueprint="service",
        title="repo-one",
        team=[],
        properties={
            "url": "https://example.com/repo-one",
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
            "defaultBranch": "master",
        },
        relations={},
    ),
]

event_data_for_three_entities_for_repository_resource = [
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

webHook_event_data_for_creation = WebhookEventData(
    kind="repository",
    data=event_data_for_three_entities_for_repository_resource,
)

one_webHook_event_data_for_creation = WebhookEventData(
    kind="repository",
    data=[
        {
            "name": "repo-one",
            "links": {"html": {"href": "https://example.com/repo-one"}},
            "main_branch": "main",
        }
    ],
)


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
                        "defaultBranch": ".main_branch",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def mock_repository_resource_config_not_passong_selector() -> ResourceConfig:
    return ResourceConfig(
        kind="repository",
        selector=Selector(query="false"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    title=".name",
                    blueprint='"service"',
                    properties={
                        "url": ".links.html.href",
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
def mock_port_app_config_with_repository_resource_not_passing_selector(
    mock_repository_resource_config_not_passong_selector: ResourceConfig,
) -> PortAppConfig:
    return PortAppConfig(
        enable_merge_entity=True,
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        resources=[mock_repository_resource_config_not_passong_selector],
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
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.return_value = mock_port_app_config_with_repository_resource  # type: ignore

    async with event_context("test_event") as event:
        event.port_app_config = mock_port_app_config_with_repository_resource
        result = await mock_live_events_mixin._get_live_event_resources("repository")

    assert len(result) == 1
    assert result[0].kind == "repository"


@pytest.mark.asyncio
async def test_getLiveEventResources_mappingDoesNotHaveTheResource_returnsEmptyList(
    mock_live_events_mixin: LiveEventsMixin,
    mock_port_app_config_with_repository_resource: PortAppConfig,
) -> None:
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.return_value = mock_port_app_config_with_repository_resource  # type: ignore

    async with event_context("test_event") as event:
        event.port_app_config = mock_port_app_config_with_repository_resource
        result = await mock_live_events_mixin._get_live_event_resources("project")

    assert len(result) == 0


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
    input_data = [
        (
            mock_repository_resource_config,
            event_data_for_three_entities_for_repository_resource,
        )
    ]

    result = await mock_live_events_mixin._calculate_raw(input_data)

    assert len(result[0].entity_selector_diff.passed) == 3
    for expected, actual in zip(
        expected_entities, result[0].entity_selector_diff.passed
    ):
        assert expected == actual


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor.parse_items"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
async def test_export_oneEntityParsedAndUpserted_returnsSuccessAndTheEntity(
    mock_upsert: AsyncMock,
    mock_parse_items: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    mock_parse_items.return_value = CalculationResult(
        entity_selector_diff=EntitySelectorDiff(passed=[entity], failed=[]),
        errors=[],
        misonfigured_entity_keys={},
    )
    mock_upsert.return_value = list[entity]  # type: ignore

    success, exported_entities = await mock_live_events_mixin._export(
        mock_repository_resource_config, {}
    )

    assert success is True
    assert exported_entities == list[entity]  # type: ignore
    mock_parse_items.assert_called_once()
    mock_upsert.assert_called_once()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor.parse_items"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
async def test_export_noEntitiesParsed_returnesSuccessAndEmptyList(
    mock_upsert: AsyncMock,
    mock_parse_items: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    mock_parse_items.return_value = CalculationResult(
        entity_selector_diff=EntitySelectorDiff(passed=[], failed=[]),
        errors=[],
        misonfigured_entity_keys={},
    )
    mock_upsert.return_value = []

    success, exported_entities = await mock_live_events_mixin._export(
        mock_repository_resource_config, {}
    )

    assert success is True
    assert exported_entities == []
    mock_parse_items.assert_called_once()
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor.parse_items"
)
async def test_export_failureWhenTringToExport_returnsFailureAndEmptyList(
    mock_parse_items: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    mock_parse_items.side_effect = Exception("Test error")

    success, exported_entities = await mock_live_events_mixin._export(
        mock_repository_resource_config, {}
    )

    assert success is False
    assert exported_entities == []


@pytest.mark.asyncio
@patch(
    "port_ocean.context.ocean.ocean.port_client.search_entities", new_callable=AsyncMock
)
async def test_isEntityExists_returnsTrue(
    mock_search_entities: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
) -> None:
    entity = Entity(
        identifier="test",
        blueprint="test_bp",
        title="test",
        team=[],
        properties={},
        relations={},
    )
    mock_search_entities.return_value = [entity]

    result = await mock_live_events_mixin._is_entity_exists(entity)

    assert result is True
    mock_search_entities.assert_called_once()


@pytest.mark.asyncio
@patch(
    "port_ocean.context.ocean.ocean.port_client.search_entities", new_callable=AsyncMock
)
async def test_isEntityExists_returnsFalse(
    mock_search_entities: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
) -> None:
    entity = Entity(
        identifier="test",
        blueprint="test_bp",
        title="test",
        team=[],
        properties={},
        relations={},
    )
    mock_search_entities.return_value = []

    result = await mock_live_events_mixin._is_entity_exists(entity)

    assert result is False
    mock_search_entities.assert_called_once()


def test_allEntitiesFilteredOutAtExport_testMultipleCases(
    mock_live_events_mixin: LiveEventsMixin,
) -> None:
    assert mock_live_events_mixin._all_entities_filtered_out_at_exort(True, []) is True
    assert (
        mock_live_events_mixin._all_entities_filtered_out_at_exort(False, []) is False
    )
    assert (
        mock_live_events_mixin._all_entities_filtered_out_at_exort(
            True,
            [
                Entity(
                    identifier="test",
                    blueprint="test_bp",
                    title="test",
                    team=[],
                    properties={},
                    relations={},
                )
            ],
        )
        is False
    )
    assert (
        mock_live_events_mixin._all_entities_filtered_out_at_exort(
            False,
            [
                Entity(
                    identifier="test",
                    blueprint="test_bp",
                    title="test",
                    team=[],
                    properties={},
                    relations={},
                )
            ],
        )
        is False
    )


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor.parse_items"
)
async def test_getEntitiesToDelete_failedEntity_returnsTheEntity(
    mock_parse_items: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    mock_parse_items.return_value = CalculationResult(
        entity_selector_diff=EntitySelectorDiff(failed=[entity], passed=[]),
        errors=[],
        misonfigured_entity_keys={},
    )

    with patch.object(mock_live_events_mixin, "_is_entity_exists", return_value=True):
        result = await mock_live_events_mixin._get_entities_to_delete(
            mock_repository_resource_config, {}
        )

        assert result == [entity]
        mock_parse_items.assert_called_once()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor.parse_items"
)
async def test_getEntitiesToDelete_failedEntityThatNotExsists_returnsEmptyList(
    mock_parse_items: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    mock_parse_items.return_value = CalculationResult(
        entity_selector_diff=EntitySelectorDiff(failed=[entity], passed=[]),
        errors=[],
        misonfigured_entity_keys={},
    )

    with patch.object(mock_live_events_mixin, "_is_entity_exists", return_value=False):
        result = await mock_live_events_mixin._get_entities_to_delete(
            mock_repository_resource_config, {}
        )

        assert result == []
        mock_parse_items.assert_called_once()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor.parse_items"
)
async def test_getEntitiesToDelete_noFailedEntity_returnsEmptyList(
    mock_parse_items: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    mock_parse_items.return_value = CalculationResult(
        entity_selector_diff=EntitySelectorDiff(failed=[], passed=[]),
        errors=[],
        misonfigured_entity_keys={},
    )

    with patch.object(mock_live_events_mixin, "_is_entity_exists", return_value=True):
        result = await mock_live_events_mixin._get_entities_to_delete(
            mock_repository_resource_config, {}
        )

        assert result == []
        mock_parse_items.assert_called_once()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor.parse_items"
)
async def test_getEntitiesToDelete_noFailedEntityAndNotExsists_returnsEmptyList(
    mock_parse_items: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_repository_resource_config: ResourceConfig,
) -> None:
    mock_parse_items.return_value = CalculationResult(
        entity_selector_diff=EntitySelectorDiff(failed=[], passed=[]),
        errors=[],
        misonfigured_entity_keys={},
    )

    with patch.object(mock_live_events_mixin, "_is_entity_exists", return_value=False):
        result = await mock_live_events_mixin._get_entities_to_delete(
            mock_repository_resource_config, {}
        )

        assert result == []
        mock_parse_items.assert_called_once()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.context.ocean.ocean.port_client.search_entities", new_callable=AsyncMock
)
async def test_processData_singleWebhookEvent_entityUpsertedAndNoDelete(
    mock_search_entities: AsyncMock,
    mock_upsert: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_port_app_config_with_repository_resource: PortAppConfig,
) -> None:

    mock_search_entities.return_value = [entity]
    mock_upsert.return_value = [entity]
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.return_value = mock_port_app_config_with_repository_resource  # type: ignore
    mock_live_events_mixin._entities_state_applier.delete = AsyncMock()  # type: ignore

    async with event_context("test_event") as event:
        event.port_app_config = mock_port_app_config_with_repository_resource
        await mock_live_events_mixin.process_data([one_webHook_event_data_for_creation])

    assert mock_upsert.call_count == 1
    assert mock_live_events_mixin._entities_state_applier.delete.call_count == 0  # type: ignore


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.context.ocean.ocean.port_client.search_entities", new_callable=AsyncMock
)
async def test_processData_singleWebhookEvent_entityDeleted(
    mock_search_entities: AsyncMock,
    mock_upsert: AsyncMock,
    mock_live_events_mixin: LiveEventsMixin,
    mock_port_app_config_with_repository_resource_not_passing_selector: PortAppConfig,
) -> None:

    mock_search_entities.return_value = [entity]
    mock_upsert.return_value = [entity]
    mock_live_events_mixin._port_app_config_handler.get_port_app_config.return_value = mock_port_app_config_with_repository_resource_not_passing_selector  # type: ignore
    mock_live_events_mixin._entities_state_applier.delete = AsyncMock()  # type: ignore

    with patch.object(mock_live_events_mixin, "_is_entity_exists", return_value=True):
        async with event_context("test_event") as event:
            event.port_app_config = (
                mock_port_app_config_with_repository_resource_not_passing_selector
            )
            await mock_live_events_mixin.process_data(
                [one_webHook_event_data_for_creation]
            )

        assert mock_upsert.call_count == 0
        assert mock_live_events_mixin._entities_state_applier.delete.call_count == 1  # type: ignore
