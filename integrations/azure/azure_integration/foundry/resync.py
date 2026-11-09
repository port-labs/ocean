from __future__ import annotations

from typing import Any, AsyncIterator, Callable, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import create_foundry_client
from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.exporters.conversations_exporter import (
    ConversationsExporter,
)
from azure_integration.foundry.core.exporters.memory_stores_exporter import (
    MemoryStoresExporter,
)
from azure_integration.foundry.core.exporters.model_deployments_exporter import (
    ModelDeploymentsExporter,
)
from azure_integration.foundry.core.exporters.project_exporter import ProjectExporter
from azure_integration.foundry.core.exporters.responses_exporter import (
    ResponsesExporter,
)
from azure_integration.foundry.core.options import (
    ListAgentsOptions,
    ListConversationsOptions,
    ListMemoryStoresOptions,
    ListModelDeploymentsOptions,
    ListResponsesOptions,
)
from azure_integration.foundry.kinds import (
    AgentResourceConfig,
    ConversationResourceConfig,
    FoundryProjectResourceConfig,
    MemoryStoreResourceConfig,
    ModelDeploymentResourceConfig,
    ObjectKind,
    ResponseResourceConfig,
)


async def resync_foundry_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(FoundryProjectResourceConfig, event.resource_config).selector
    async for batch in ProjectExporter().get_paginated_resources(
        api_version=selector.api_version
    ):
        if batch:
            yield batch


async def resync_foundry_agents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(AgentResourceConfig, event.resource_config).selector
    exporter = AgentsExporter(create_foundry_client())

    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects:
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry agents for project {project['name']} ({project_endpoint})"
            )
            async for page in exporter.get_paginated_resources(
                ListAgentsOptions(
                    project_endpoint=project_endpoint,
                    project_id=str(project["id"]),
                    include_versions=selector.include_versions,
                )
            ):
                yield page


async def resync_foundry_model_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ModelDeploymentResourceConfig, event.resource_config).selector
    exporter = ModelDeploymentsExporter(create_foundry_client())

    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects:
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry deployments for project {project['name']} ({project_endpoint})"
            )
            async for page in exporter.get_paginated_resources(
                ListModelDeploymentsOptions(
                    project_endpoint=project_endpoint,
                    project_id=str(project["id"]),
                )
            ):
                yield page


async def resync_foundry_conversations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ConversationResourceConfig, event.resource_config).selector
    exporter = ConversationsExporter(create_foundry_client())

    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects:
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry conversations for project {project['name']} ({project_endpoint})"
            )
            async for page in exporter.get_paginated_resources(
                ListConversationsOptions(
                    project_endpoint=project_endpoint,
                    project_id=str(project["id"]),
                    since_days=selector.since_days,
                )
            ):
                yield page


async def resync_foundry_responses(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ResponseResourceConfig, event.resource_config).selector
    exporter = ResponsesExporter(create_foundry_client())

    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects:
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry responses for project {project['name']} ({project_endpoint})"
            )
            async for page in exporter.get_paginated_resources(
                ListResponsesOptions(
                    project_endpoint=project_endpoint,
                    project_id=str(project["id"]),
                    since_days=selector.since_days,
                )
            ):
                yield page


async def resync_foundry_memory_stores(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(MemoryStoreResourceConfig, event.resource_config).selector
    exporter = MemoryStoresExporter(create_foundry_client())

    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects:
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry memory stores for project {project['name']} ({project_endpoint})"
            )
            async for page in exporter.get_paginated_resources(
                ListMemoryStoresOptions(
                    project_endpoint=project_endpoint,
                    project_id=str(project["id"]),
                )
            ):
                yield page


FOUNDRY_RESYNC_HANDLERS: dict[
    str, Callable[[str], AsyncIterator[list[dict[str, Any]]]]
] = {
    ObjectKind.FOUNDRY_PROJECT: resync_foundry_projects,
    ObjectKind.AGENT: resync_foundry_agents,
    ObjectKind.MODEL_DEPLOYMENT: resync_foundry_model_deployments,
    ObjectKind.CONVERSATION: resync_foundry_conversations,
    ObjectKind.RESPONSE: resync_foundry_responses,
    ObjectKind.MEMORY_STORE: resync_foundry_memory_stores,
}
