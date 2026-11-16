from __future__ import annotations

from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import (
    FoundryApiError,
    create_foundry_client,
)
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
from azure_integration.foundry.core.exporters.skills_exporter import SkillsExporter
from azure_integration.foundry.core.exporters.toolboxes_exporter import (
    ToolboxesExporter,
)
from azure_integration.foundry.core.options import (
    ListAgentsOptions,
    ListConversationsOptions,
    ListMemoryStoresOptions,
    ListModelDeploymentsOptions,
    ListResponsesOptions,
    ListSkillsOptions,
    ListToolboxesOptions,
)
from azure_integration.foundry.kinds import (
    AgentResourceConfig,
    ConversationResourceConfig,
    FoundryProjectResourceConfig,
    MemoryStoreResourceConfig,
    ModelDeploymentResourceConfig,
    ObjectKind,
    ResponseResourceConfig,
    SkillResourceConfig,
    ToolboxResourceConfig,
)
from azure_integration.foundry.helpers.utils import projects_matching_regions


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_PROJECT)
@ocean.on_resync(ObjectKind.FOUNDRY_PROJECT)
async def resync_foundry_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(FoundryProjectResourceConfig, event.resource_config).selector
    async for batch in ProjectExporter().get_paginated_resources(
        api_version=selector.api_version
    ):
        if batch:
            yield batch


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_AGENT)
@ocean.on_resync(ObjectKind.FOUNDRY_AGENT)
async def resync_foundry_agents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(AgentResourceConfig, event.resource_config).selector
    exporter = AgentsExporter(create_foundry_client(selector.api_version))

    regions = list(selector.project.regions)
    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects_matching_regions(projects, regions):
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


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_MODEL_DEPLOYMENT)
@ocean.on_resync(ObjectKind.FOUNDRY_MODEL_DEPLOYMENT)
async def resync_foundry_model_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ModelDeploymentResourceConfig, event.resource_config).selector
    exporter = ModelDeploymentsExporter(create_foundry_client(selector.api_version))

    regions = list(selector.project.regions)
    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects_matching_regions(projects, regions):
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


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_CONVERSATION)
@ocean.on_resync(ObjectKind.FOUNDRY_CONVERSATION)
async def resync_foundry_conversations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ConversationResourceConfig, event.resource_config).selector
    exporter = ConversationsExporter(create_foundry_client(selector.api_version))

    regions = list(selector.project.regions)
    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects_matching_regions(projects, regions):
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry conversations for project {project['name']} ({project_endpoint})"
            )
            async for page in exporter.get_paginated_resources(
                ListConversationsOptions(
                    project_endpoint=project_endpoint,
                    project_id=str(project["id"]),
                    since_days=selector.since_days,
                    endpoint_scopes=list(selector.endpoint_scopes),
                )
            ):
                yield page


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_RESPONSE)
@ocean.on_resync(ObjectKind.FOUNDRY_RESPONSE)
async def resync_foundry_responses(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ResponseResourceConfig, event.resource_config).selector
    exporter = ResponsesExporter(create_foundry_client(selector.api_version))

    regions = list(selector.project.regions)
    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects_matching_regions(projects, regions):
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry responses for project {project['name']} ({project_endpoint})"
            )
            async for page in exporter.get_paginated_resources(
                ListResponsesOptions(
                    project_endpoint=project_endpoint,
                    project_id=str(project["id"]),
                    since_days=selector.since_days,
                    endpoint_scopes=list(selector.endpoint_scopes),
                )
            ):
                yield page


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_MEMORY_STORE)
@ocean.on_resync(ObjectKind.FOUNDRY_MEMORY_STORE)
async def resync_foundry_memory_stores(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(MemoryStoreResourceConfig, event.resource_config).selector
    exporter = MemoryStoresExporter(create_foundry_client(selector.api_version))

    regions = list(selector.project.regions)
    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects_matching_regions(projects, regions):
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


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_SKILL)
@ocean.on_resync(ObjectKind.FOUNDRY_SKILL)
async def resync_foundry_skills(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(SkillResourceConfig, event.resource_config).selector
    exporter = SkillsExporter(create_foundry_client(selector.api_version))

    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects_matching_regions(projects, selector.project.regions):
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry skills for project {project['name']} ({project_endpoint})"
            )
            try:
                async for page in exporter.get_paginated_resources(
                    ListSkillsOptions(
                        project_endpoint=project_endpoint,
                        project_id=str(project["id"]),
                    )
                ):
                    yield page
            except FoundryApiError as exc:
                logger.warning(
                    f"Skipping Foundry skills for project {project['name']}: {exc}"
                )


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_TOOLBOX)
@ocean.on_resync(ObjectKind.FOUNDRY_TOOLBOX)
async def resync_foundry_toolboxes(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ToolboxResourceConfig, event.resource_config).selector
    exporter = ToolboxesExporter(create_foundry_client(selector.api_version))

    async for projects in ProjectExporter().get_paginated_resources(
        api_version=selector.project.api_version
    ):
        for project in projects_matching_regions(projects, selector.project.regions):
            project_endpoint = str(project["__foundryProjectEndpoint"])
            logger.info(
                f"Syncing Foundry toolboxes for project {project['name']} ({project_endpoint})"
            )
            try:
                async for page in exporter.get_paginated_resources(
                    ListToolboxesOptions(
                        project_endpoint=project_endpoint,
                        project_id=str(project["id"]),
                    )
                ):
                    yield page
            except FoundryApiError as exc:
                logger.warning(
                    f"Skipping Foundry toolboxes for project {project['name']}: {exc}"
                )
