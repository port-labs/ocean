from __future__ import annotations

from typing import cast

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import (
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
    async for page in exporter.get_paginated_resources_across_projects(
        resource_label="agents",
        project_api_version=selector.project.api_version,
        regions=list(selector.project.regions),
        build_options=lambda ep, pid: ListAgentsOptions(
            project_endpoint=ep,
            project_id=pid,
            include_versions=selector.include_versions,
        ),
    ):
        yield page


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_MODEL_DEPLOYMENT)
@ocean.on_resync(ObjectKind.FOUNDRY_MODEL_DEPLOYMENT)
async def resync_foundry_model_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ModelDeploymentResourceConfig, event.resource_config).selector
    exporter = ModelDeploymentsExporter(create_foundry_client(selector.api_version))
    async for page in exporter.get_paginated_resources_across_projects(
        resource_label="deployments",
        project_api_version=selector.project.api_version,
        regions=list(selector.project.regions),
        build_options=lambda ep, pid: ListModelDeploymentsOptions(
            project_endpoint=ep, project_id=pid
        ),
    ):
        yield page


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_CONVERSATION)
@ocean.on_resync(ObjectKind.FOUNDRY_CONVERSATION)
async def resync_foundry_conversations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ConversationResourceConfig, event.resource_config).selector
    exporter = ConversationsExporter(create_foundry_client(selector.api_version))
    async for page in exporter.get_paginated_resources_across_projects(
        resource_label="conversations",
        project_api_version=selector.project.api_version,
        regions=list(selector.project.regions),
        build_options=lambda ep, pid: ListConversationsOptions(
            project_endpoint=ep,
            project_id=pid,
            since_days=selector.since_days,
            endpoint_scopes=list(selector.endpoint_scopes),
        ),
    ):
        yield page


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_RESPONSE)
@ocean.on_resync(ObjectKind.FOUNDRY_RESPONSE)
async def resync_foundry_responses(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ResponseResourceConfig, event.resource_config).selector
    exporter = ResponsesExporter(create_foundry_client(selector.api_version))
    async for page in exporter.get_paginated_resources_across_projects(
        resource_label="responses",
        project_api_version=selector.project.api_version,
        regions=list(selector.project.regions),
        build_options=lambda ep, pid: ListResponsesOptions(
            project_endpoint=ep,
            project_id=pid,
            since_days=selector.since_days,
            endpoint_scopes=list(selector.endpoint_scopes),
        ),
    ):
        yield page


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_MEMORY_STORE)
@ocean.on_resync(ObjectKind.FOUNDRY_MEMORY_STORE)
async def resync_foundry_memory_stores(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(MemoryStoreResourceConfig, event.resource_config).selector
    exporter = MemoryStoresExporter(create_foundry_client(selector.api_version))
    async for page in exporter.get_paginated_resources_across_projects(
        resource_label="memory stores",
        project_api_version=selector.project.api_version,
        regions=list(selector.project.regions),
        build_options=lambda ep, pid: ListMemoryStoresOptions(
            project_endpoint=ep, project_id=pid
        ),
    ):
        yield page


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_SKILL)
@ocean.on_resync(ObjectKind.FOUNDRY_SKILL)
async def resync_foundry_skills(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(SkillResourceConfig, event.resource_config).selector
    exporter = SkillsExporter(create_foundry_client(selector.api_version))
    async for page in exporter.get_paginated_resources_across_projects(
        resource_label="skills",
        project_api_version=selector.project.api_version,
        regions=list(selector.project.regions),
        build_options=lambda ep, pid: ListSkillsOptions(
            project_endpoint=ep, project_id=pid
        ),
    ):
        yield page


@ocean.on_incremental_resync(ObjectKind.FOUNDRY_TOOLBOX)
@ocean.on_resync(ObjectKind.FOUNDRY_TOOLBOX)
async def resync_foundry_toolboxes(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ToolboxResourceConfig, event.resource_config).selector
    exporter = ToolboxesExporter(create_foundry_client(selector.api_version))
    async for page in exporter.get_paginated_resources_across_projects(
        resource_label="toolboxes",
        project_api_version=selector.project.api_version,
        regions=list(selector.project.regions),
        build_options=lambda ep, pid: ListToolboxesOptions(
            project_endpoint=ep, project_id=pid
        ),
    ):
        yield page
