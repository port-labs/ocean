from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from httpx import Response

from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import IntegrationSettings, MetricsSettings
from port_ocean.context.event import EventContext
from port_ocean.context.ocean import PortOceanContext, ocean
from port_ocean.core.handlers.entities_state_applier.port.applier import (
    HttpEntitiesStateApplier,
)
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.models import Entity, ProcessExecutionMode
from port_ocean.helpers.metric.metric import Metrics
from port_ocean.ocean import Ocean
from port_ocean.cache.memory import InMemoryCacheProvider


@pytest.fixture
def mock_http_client() -> MagicMock:
    mock_http_client = MagicMock()
    mock_upserted_entities = []

    async def post(url: str, *args: Any, **kwargs: Any) -> Response:
        if "/bulk" in url:
            success_entities = []
            failed_entities = []
            entities_body = kwargs.get("json", {})
            entities = entities_body.get("entities", [])
            for index, entity in enumerate(entities):
                if entity.get("properties", {}).get("mock_is_to_fail", False):
                    failed_entities.append(
                        {
                            "identifier": entity.get("identifier"),
                            "index": index,
                            "statusCode": 404,
                            "error": "not_found",
                            "message": "Entity not found",
                        }
                    )
                else:
                    mock_upserted_entities.append(
                        f"{entity.get('identifier')}-{entity.get('blueprint')}"
                    )
                    success_entities.append(
                        (
                            {
                                "identifier": entity.get("identifier"),
                                "index": index,
                                "created": True,
                            }
                        )
                    )

            return Response(
                207,
                json={"entities": success_entities, "errors": failed_entities},
            )
        else:
            entity = kwargs.get("json", {})
            if entity.get("properties", {}).get("mock_is_to_fail", False):
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
        ocean_mock.process_execution_mode = ProcessExecutionMode.single_process
        ocean_mock.cache_provider = InMemoryCacheProvider()
        metrics_settings = MetricsSettings(enabled=True)
        integration_settings = IntegrationSettings(type="test", identifier="test")
        ocean_mock.metrics = Metrics(
            metrics_settings=metrics_settings,
            integration_configuration=integration_settings,
            port_client=mock_port_client,
        )

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
def mock_resource_config() -> ResourceConfig:
    resource = ResourceConfig(
        kind="service",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"service"',
                    properties={"url": ".web_url"},
                    relations={},
                )
            )
        ),
    )
    return resource


@pytest.fixture
def mock_entities_state_applier(
    mock_context: PortOceanContext,
) -> HttpEntitiesStateApplier:
    return HttpEntitiesStateApplier(mock_context)


@asynccontextmanager
async def no_op_event_context(
    existing_event: EventContext,
) -> AsyncGenerator[EventContext, None]:
    yield existing_event


def create_entity(
    id: str,
    blueprint: str,
    relation: dict[str, str] | None = None,
    is_to_fail: bool = False,
    team: str | list[str] | dict[str, Any] | None = None,
) -> Entity:
    if relation is None:
        relation = {}
    entity = Entity(identifier=id, blueprint=blueprint, team=team)
    entity.relations = relation
    entity.properties = {"mock_is_to_fail": is_to_fail}
    return entity
