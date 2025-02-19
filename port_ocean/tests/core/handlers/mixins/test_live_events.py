from typing import Any
from httpx import Response
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.entities_state_applier.port.applier import (
    HttpEntitiesStateApplier,
)
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
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


one_webhook_event_raw_results_for_creation = WebhookEventRawResults(
    updated_raw_results=[
        {
            "name": "repo-one",
            "links": {"html": {"href": "https://example.com/repo-one"}},
            "main_branch": "main",
        }
    ],
    deleted_raw_results=[],
)
one_webhook_event_raw_results_for_creation.resource = ResourceConfig(
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
one_webhook_event_raw_results_for_deletion = WebhookEventRawResults(
    deleted_raw_results=[
        {
            "name": "repo-one",
            "links": {"html": {"href": "https://example.com/repo-one"}},
            "main_branch": "main",
        }
    ],
    updated_raw_results=[],
)
one_webhook_event_raw_results_for_deletion.resource = ResourceConfig(
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
async def test_parse_raw_event_results_to_entities_creation(
    mock_live_events_mixin: LiveEventsMixin,
) -> None:
    """Test parsing raw event results for entity creation"""
    mock_live_events_mixin.entity_processor.parse_items = AsyncMock()  # type: ignore

    calculation_result = CalculationResult(
        entity_selector_diff=EntitySelectorDiff(passed=[entity], failed=[]),
        errors=[],
        misonfigured_entity_keys={},
    )
    mock_live_events_mixin.entity_processor.parse_items.return_value = (
        calculation_result
    )

    entities_to_create, entities_to_delete = (
        await mock_live_events_mixin._parse_raw_event_results_to_entities(
            [one_webhook_event_raw_results_for_creation]
        )
    )

    assert entities_to_create == [entity]
    assert entities_to_delete == []
    mock_live_events_mixin.entity_processor.parse_items.assert_called_once()


@pytest.mark.asyncio
async def test_parse_raw_event_results_to_entities_deletion(
    mock_live_events_mixin: LiveEventsMixin,
) -> None:
    """Test parsing raw event results for entity deletion"""
    mock_live_events_mixin.entity_processor.parse_items = AsyncMock()  # type: ignore

    calculation_result = CalculationResult(
        entity_selector_diff=EntitySelectorDiff(passed=[entity], failed=[]),
        errors=[],
        misonfigured_entity_keys={},
    )
    mock_live_events_mixin.entity_processor.parse_items.return_value = (
        calculation_result
    )

    entities_to_create, entities_to_delete = (
        await mock_live_events_mixin._parse_raw_event_results_to_entities(
            [one_webhook_event_raw_results_for_deletion]
        )
    )

    assert entities_to_create == []
    assert entities_to_delete == [entity]
    mock_live_events_mixin.entity_processor.parse_items.assert_called_once()


@pytest.mark.asyncio
async def test_sync_raw_results_one_raw_result_entity_upserted(
    mock_live_events_mixin: LiveEventsMixin,
) -> None:
    """Test synchronizing raw webhook event results"""
    # Setup mocks
    mock_live_events_mixin._parse_raw_event_results_to_entities = AsyncMock(return_value=([entity], []))  # type: ignore
    mock_live_events_mixin.entities_state_applier.upsert = AsyncMock()  # type: ignore
    mock_live_events_mixin.entities_state_applier.delete = AsyncMock()  # type: ignore
    mock_live_events_mixin._delete_entities = AsyncMock()  # type: ignore

    # Call the method
    await mock_live_events_mixin.sync_raw_results(
        [one_webhook_event_raw_results_for_creation]
    )

    # Verify the method calls
    mock_live_events_mixin._parse_raw_event_results_to_entities.assert_called_once_with(
        [one_webhook_event_raw_results_for_creation]
    )
    mock_live_events_mixin.entities_state_applier.upsert.assert_called_once_with(
        [entity], UserAgentType.exporter
    )
    mock_live_events_mixin.entities_state_applier.delete.assert_not_called()
