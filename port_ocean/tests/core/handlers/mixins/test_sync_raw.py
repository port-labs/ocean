from contextlib import asynccontextmanager
from graphlib import CycleError
from typing import Any, AsyncGenerator

from httpx import Response
from port_ocean.clients.port.client import PortClient
from port_ocean.core.utils.entity_topological_sorter import EntityTopologicalSorter
from port_ocean.exceptions.core import OceanAbortException
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from port_ocean.ocean import Ocean
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.mixins import SyncRawMixin
from port_ocean.core.handlers.entities_state_applier.port.applier import (
    HttpEntitiesStateApplier,
)
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.models import Entity
from port_ocean.context.event import EventContext, event_context, EventType
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.ocean import ocean


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
def mock_context(mock_ocean: Ocean) -> PortOceanContext:
    context = PortOceanContext(mock_ocean)
    ocean._app = context.app
    return context


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

    async def get_config(use_cache: bool = True) -> Any:
        return mock_port_app_config

    handler.get_port_app_config = get_config
    return handler


@pytest.fixture
def mock_entity_processor(mock_context: PortOceanContext) -> JQEntityProcessor:
    return JQEntityProcessor(mock_context)


@pytest.fixture
def mock_entities_state_applier(
    mock_context: PortOceanContext,
) -> HttpEntitiesStateApplier:
    return HttpEntitiesStateApplier(mock_context)


@pytest.fixture
def mock_sync_raw_mixin(
    mock_entity_processor: JQEntityProcessor,
    mock_entities_state_applier: HttpEntitiesStateApplier,
    mock_port_app_config_handler: MagicMock,
) -> SyncRawMixin:
    sync_raw_mixin = SyncRawMixin()
    sync_raw_mixin._entity_processor = mock_entity_processor
    sync_raw_mixin._entities_state_applier = mock_entities_state_applier
    sync_raw_mixin._port_app_config_handler = mock_port_app_config_handler
    sync_raw_mixin._get_resource_raw_results = AsyncMock(return_value=([{}], []))  # type: ignore
    sync_raw_mixin._entity_processor.parse_items = AsyncMock(return_value=MagicMock())  # type: ignore

    return sync_raw_mixin


@pytest.fixture
def mock_sync_raw_mixin_with_jq_processor(
    mock_sync_raw_mixin: SyncRawMixin,
) -> SyncRawMixin:
    mock_sync_raw_mixin._entity_processor = JQEntityProcessor(mock_context)  # type: ignore
    return mock_sync_raw_mixin


@asynccontextmanager
async def no_op_event_context(
    existing_event: EventContext,
) -> AsyncGenerator[EventContext, None]:
    yield existing_event


def create_entity(
    id: str, blueprint: str, relation: dict[str, str], is_to_fail: bool
) -> Entity:
    entity = Entity(identifier=id, blueprint=blueprint)
    entity.relations = relation
    entity.properties = {"mock_is_to_fail": is_to_fail}
    return entity


@pytest.mark.asyncio
async def test_sync_raw_mixin_self_dependency(
    mock_sync_raw_mixin: SyncRawMixin,
) -> None:
    entities_params = [
        ("entity_1", "service", {"service": "entity_1"}, True),
        ("entity_2", "service", {"service": "entity_2"}, False),
    ]
    entities = [create_entity(*entity_param) for entity_param in entities_params]

    calc_result_mock = MagicMock()
    calc_result_mock.entity_selector_diff.passed = entities
    calc_result_mock.errors = []

    mock_sync_raw_mixin.entity_processor.parse_items = AsyncMock(return_value=calc_result_mock)  # type: ignore

    mock_order_by_entities_dependencies = MagicMock(
        side_effect=EntityTopologicalSorter.order_by_entities_dependencies
    )
    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        app_config = (
            await mock_sync_raw_mixin.port_app_config_handler.get_port_app_config(
                use_cache=False
            )
        )
        event.port_app_config = app_config
        event.entity_topological_sorter.register_entity = MagicMock(side_effect=event.entity_topological_sorter.register_entity)  # type: ignore
        event.entity_topological_sorter.get_entities = MagicMock(side_effect=event.entity_topological_sorter.get_entities)  # type: ignore

        with patch(
            "port_ocean.core.integrations.mixins.sync_raw.event_context",
            lambda *args, **kwargs: no_op_event_context(event),
        ):
            with patch(
                "port_ocean.core.utils.entity_topological_sorter.EntityTopologicalSorter.order_by_entities_dependencies",
                mock_order_by_entities_dependencies,
            ):

                await mock_sync_raw_mixin.sync_raw_all(
                    trigger_type="machine", user_agent_type=UserAgentType.exporter
                )

                assert (
                    len(event.entity_topological_sorter.entities) == 1
                ), "Expected one failed entity callback due to retry logic"
                assert event.entity_topological_sorter.register_entity.call_count == 1
                assert event.entity_topological_sorter.get_entities.call_count == 1

                assert mock_order_by_entities_dependencies.call_count == 1
                assert [
                    call[0][0][0]
                    for call in mock_order_by_entities_dependencies.call_args_list
                ] == [entity for entity in entities if entity.identifier == "entity_1"]


@pytest.mark.asyncio
async def test_sync_raw_mixin_circular_dependency(
    mock_sync_raw_mixin: SyncRawMixin, mock_ocean: Ocean
) -> None:
    entities_params = [
        ("entity_1", "service", {"service": "entity_2"}, True),
        ("entity_2", "service", {"service": "entity_1"}, True),
    ]
    entities = [create_entity(*entity_param) for entity_param in entities_params]

    calc_result_mock = MagicMock()
    calc_result_mock.entity_selector_diff.passed = entities
    calc_result_mock.errors = []

    mock_sync_raw_mixin.entity_processor.parse_items = AsyncMock(return_value=calc_result_mock)  # type: ignore

    mock_order_by_entities_dependencies = MagicMock(
        side_effect=EntityTopologicalSorter.order_by_entities_dependencies
    )
    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        app_config = (
            await mock_sync_raw_mixin.port_app_config_handler.get_port_app_config(
                use_cache=False
            )
        )
        event.port_app_config = app_config
        org = event.entity_topological_sorter.register_entity

        def mock_register_entity(*args: Any, **kwargs: Any) -> Any:
            entity = args[0]
            entity.properties["mock_is_to_fail"] = False
            return org(*args, **kwargs)

        event.entity_topological_sorter.register_entity = MagicMock(side_effect=mock_register_entity)  # type: ignore
        raiesed_error_handle_failed = []
        org_get_entities = event.entity_topological_sorter.get_entities

        def handle_failed_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return list(org_get_entities(*args, **kwargs))
            except Exception as e:
                raiesed_error_handle_failed.append(e)
                raise e

        event.entity_topological_sorter.get_entities = MagicMock(side_effect=lambda *args, **kwargs: handle_failed_wrapper(*args, **kwargs))  # type: ignore

        with patch(
            "port_ocean.core.integrations.mixins.sync_raw.event_context",
            lambda *args, **kwargs: no_op_event_context(event),
        ):
            with patch(
                "port_ocean.core.utils.entity_topological_sorter.EntityTopologicalSorter.order_by_entities_dependencies",
                mock_order_by_entities_dependencies,
            ):

                await mock_sync_raw_mixin.sync_raw_all(
                    trigger_type="machine", user_agent_type=UserAgentType.exporter
                )

                assert (
                    len(event.entity_topological_sorter.entities) == 2
                ), "Expected one failed entity callback due to retry logic"
                assert event.entity_topological_sorter.register_entity.call_count == 2
                assert event.entity_topological_sorter.get_entities.call_count == 2
                assert [
                    call[0]
                    for call in event.entity_topological_sorter.get_entities.call_args_list
                ] == [(), (False,)]
                assert len(raiesed_error_handle_failed) == 1
                assert isinstance(raiesed_error_handle_failed[0], OceanAbortException)
                assert isinstance(raiesed_error_handle_failed[0].__cause__, CycleError)
                assert (
                    len(mock_ocean.port_client.client.post.call_args_list)  # type: ignore
                    / len(entities)
                    == 2
                )


@pytest.mark.asyncio
async def test_sync_raw_mixin_dependency(
    mock_sync_raw_mixin: SyncRawMixin, mock_ocean: Ocean
) -> None:
    entities_params = [
        ("entity_1", "service", {"service": "entity_3"}, True),
        ("entity_2", "service", {"service": "entity_4"}, True),
        ("entity_3", "service", {"service": ""}, True),
        ("entity_4", "service", {"service": "entity_3"}, True),
        ("entity_5", "service", {"service": "entity_1"}, True),
    ]
    entities = [create_entity(*entity_param) for entity_param in entities_params]

    calc_result_mock = MagicMock()
    calc_result_mock.entity_selector_diff.passed = entities
    calc_result_mock.errors = []

    mock_sync_raw_mixin.entity_processor.parse_items = AsyncMock(return_value=calc_result_mock)  # type: ignore

    mock_order_by_entities_dependencies = MagicMock(
        side_effect=EntityTopologicalSorter.order_by_entities_dependencies
    )
    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        app_config = (
            await mock_sync_raw_mixin.port_app_config_handler.get_port_app_config(
                use_cache=False
            )
        )
        event.port_app_config = app_config
        org = event.entity_topological_sorter.register_entity

        def mock_register_entity(*args: Any, **kwargs: Any) -> None:
            entity = args[0]
            entity.properties["mock_is_to_fail"] = False
            return org(*args, **kwargs)

        event.entity_topological_sorter.register_entity = MagicMock(side_effect=mock_register_entity)  # type: ignore
        raiesed_error_handle_failed = []
        org_event_get_entities = event.entity_topological_sorter.get_entities

        def get_entities_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return org_event_get_entities(*args, **kwargs)
            except Exception as e:
                raiesed_error_handle_failed.append(e)
                raise e

        event.entity_topological_sorter.get_entities = MagicMock(side_effect=lambda *args, **kwargs: get_entities_wrapper(*args, **kwargs))  # type: ignore

        with patch(
            "port_ocean.core.integrations.mixins.sync_raw.event_context",
            lambda *args, **kwargs: no_op_event_context(event),
        ):
            with patch(
                "port_ocean.core.utils.entity_topological_sorter.EntityTopologicalSorter.order_by_entities_dependencies",
                mock_order_by_entities_dependencies,
            ):

                await mock_sync_raw_mixin.sync_raw_all(
                    trigger_type="machine", user_agent_type=UserAgentType.exporter
                )

                assert event.entity_topological_sorter.register_entity.call_count == 5
                assert (
                    len(event.entity_topological_sorter.entities) == 5
                ), "Expected one failed entity callback due to retry logic"
                assert event.entity_topological_sorter.get_entities.call_count == 1
                assert len(raiesed_error_handle_failed) == 0
                assert mock_ocean.port_client.client.post.call_count == 10  # type: ignore
                assert mock_order_by_entities_dependencies.call_count == 1

                first = mock_ocean.port_client.client.post.call_args_list[0:5]  # type: ignore
                second = mock_ocean.port_client.client.post.call_args_list[5:10]  # type: ignore

                assert "-".join(
                    [call[1].get("json").get("identifier") for call in first]
                ) == "-".join([entity.identifier for entity in entities])
                assert "-".join(
                    [call[1].get("json").get("identifier") for call in second]
                ) in (
                    "entity_3-entity_4-entity_1-entity_2-entity_5",
                    "entity_3-entity_4-entity_1-entity_5-entity_2",
                    "entity_3-entity_1-entity_4-entity_2-entity_5",
                    "entity_3-entity_1-entity_4-entity_5-entity_2",
                )


@pytest.mark.asyncio
async def test_register_raw(
    mock_sync_raw_mixin_with_jq_processor: SyncRawMixin, mock_ocean: Ocean
) -> None:
    kind = "service"
    user_agent_type = UserAgentType.exporter
    raw_entity = [
        {"id": "entity_1", "name": "entity_1", "web_url": "https://example.com"},
    ]
    expected_result = [
        {
            "identifier": "entity_1",
            "blueprint": "service",
            "name": "entity_1",
            "properties": {"url": "https://example.com"},
        },
    ]

    async with event_context(EventType.HTTP_REQUEST, trigger_type="machine") as event:
        # Use patch to mock the method instead of direct assignment
        with patch.object(
            mock_sync_raw_mixin_with_jq_processor.port_app_config_handler,
            "get_port_app_config",
            return_value=PortAppConfig(
                enable_merge_entity=True,
                delete_dependent_entities=True,
                create_missing_related_entities=False,
                resources=[
                    ResourceConfig(
                        kind=kind,
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
            ),
        ):
            # Ensure the event.port_app_config is set correctly
            event.port_app_config = await mock_sync_raw_mixin_with_jq_processor.port_app_config_handler.get_port_app_config(
                use_cache=False
            )

            def upsert_side_effect(
                entities: list[Entity], user_agent_type: UserAgentType
            ) -> list[Entity]:
                # Simulate returning the passed entities
                return entities

            # Patch the upsert method with the side effect
            with patch.object(
                mock_sync_raw_mixin_with_jq_processor.entities_state_applier,
                "upsert",
                side_effect=upsert_side_effect,
            ):
                # Call the register_raw method
                registered_entities = (
                    await mock_sync_raw_mixin_with_jq_processor.register_raw(
                        kind, raw_entity, user_agent_type
                    )
                )

                # Assert that the registered entities match the expected results
                assert len(registered_entities) == len(expected_result)
                for entity, result in zip(registered_entities, expected_result):
                    assert entity.identifier == result["identifier"]
                    assert entity.blueprint == result["blueprint"]
                    assert entity.properties == result["properties"]


@pytest.mark.asyncio
async def test_unregister_raw(
    mock_sync_raw_mixin_with_jq_processor: SyncRawMixin, mock_ocean: Ocean
) -> None:
    kind = "service"
    user_agent_type = UserAgentType.exporter
    raw_entity = [
        {"id": "entity_1", "name": "entity_1", "web_url": "https://example.com"},
    ]
    expected_result = [
        {
            "identifier": "entity_1",
            "blueprint": "service",
            "name": "entity_1",
            "properties": {"url": "https://example.com"},
        },
    ]

    async with event_context(EventType.HTTP_REQUEST, trigger_type="machine") as event:
        # Use patch to mock the method instead of direct assignment
        with patch.object(
            mock_sync_raw_mixin_with_jq_processor.port_app_config_handler,
            "get_port_app_config",
            return_value=PortAppConfig(
                enable_merge_entity=True,
                delete_dependent_entities=True,
                create_missing_related_entities=False,
                resources=[
                    ResourceConfig(
                        kind=kind,
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
            ),
        ):
            # Ensure the event.port_app_config is set correctly
            event.port_app_config = await mock_sync_raw_mixin_with_jq_processor.port_app_config_handler.get_port_app_config(
                use_cache=False
            )

            # Call the unregister_raw method
            unregistered_entities = (
                await mock_sync_raw_mixin_with_jq_processor.unregister_raw(
                    kind, raw_entity, user_agent_type
                )
            )

            # Assert that the unregistered entities match the expected results
            assert len(unregistered_entities) == len(expected_result)
            for entity, result in zip(unregistered_entities, expected_result):
                assert entity.identifier == result["identifier"]
                assert entity.blueprint == result["blueprint"]
                assert entity.properties == result["properties"]
