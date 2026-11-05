from __future__ import annotations

from typing import Any, AsyncIterator, Callable, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.discovery import (
    discover_foundry_projects,
    foundry_project_to_raw,
)
from azure_integration.foundry.exporter_factory import (
    create_agent_versions_exporter,
    create_agents_exporter,
    create_conversations_exporter,
    create_memory_stores_exporter,
    create_model_deployments_exporter,
    create_responses_exporter,
)
from azure_integration.foundry.helpers.project_scope import project_endpoint_context
from azure_integration.foundry.kinds import (
    AgentResourceConfig,
    ConversationResourceConfig,
    ObjectKind,
    ResponseResourceConfig,
)


def _stamp_project(item: dict[str, Any], *, endpoint: str, project_arm_id: str) -> dict[str, Any]:
    stamped = dict(item)
    stamped["foundryProjectEndpoint"] = endpoint
    stamped["foundryProjectId"] = project_arm_id
    return stamped


async def resync_foundry_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    projects = await discover_foundry_projects(force_refresh=True)
    batch = [foundry_project_to_raw(project) for project in projects]
    if batch:
        yield batch


async def _resync_across_projects(
    fetch_pages: Callable[[], ASYNC_GENERATOR_RESYNC_TYPE],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    projects = await discover_foundry_projects()
    if not projects:
        logger.info("No Foundry projects discovered; skipping Foundry kind resync")
        return

    for project in projects:
        logger.info(
            f"Syncing Foundry resources for project {project.project_name} "
            f"({project.endpoint})"
        )
        with project_endpoint_context(project.endpoint):
            async for page in fetch_pages():
                if page:
                    yield [
                        _stamp_project(
                            item,
                            endpoint=project.endpoint,
                            project_arm_id=project.project_arm_id,
                        )
                        for item in page
                    ]


async def resync_foundry_agents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(AgentResourceConfig, event.resource_config).selector

    async def fetch() -> ASYNC_GENERATOR_RESYNC_TYPE:
        exporter = create_agents_exporter()
        async for page in exporter.get_paginated_resources(
            include_versions=selector.include_versions,
        ):
            yield page

    async for page in _resync_across_projects(fetch):
        yield page


async def resync_foundry_agent_versions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind

    async def fetch() -> ASYNC_GENERATOR_RESYNC_TYPE:
        exporter = create_agent_versions_exporter()
        async for page in exporter.get_paginated_resources():
            yield page

    async for page in _resync_across_projects(fetch):
        yield page


async def resync_foundry_model_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind

    async def fetch() -> ASYNC_GENERATOR_RESYNC_TYPE:
        exporter = create_model_deployments_exporter()
        async for page in exporter.get_paginated_resources():
            yield page

    async for page in _resync_across_projects(fetch):
        yield page


async def resync_foundry_conversations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ConversationResourceConfig, event.resource_config).selector

    async def fetch() -> ASYNC_GENERATOR_RESYNC_TYPE:
        exporter = create_conversations_exporter()
        async for page in exporter.get_paginated_resources(since_days=selector.since_days):
            yield page

    async for page in _resync_across_projects(fetch):
        yield page


async def resync_foundry_responses(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind
    selector = cast(ResponseResourceConfig, event.resource_config).selector

    async def fetch() -> ASYNC_GENERATOR_RESYNC_TYPE:
        exporter = create_responses_exporter()
        async for page in exporter.get_paginated_resources(since_days=selector.since_days):
            yield page

    async for page in _resync_across_projects(fetch):
        yield page


async def resync_foundry_memory_stores(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del kind

    async def fetch() -> ASYNC_GENERATOR_RESYNC_TYPE:
        exporter = create_memory_stores_exporter()
        async for page in exporter.get_paginated_resources():
            yield page

    async for page in _resync_across_projects(fetch):
        yield page


FOUNDRY_RESYNC_HANDLERS: dict[str, Callable[[str], AsyncIterator[list[dict[str, Any]]]]] = {
    ObjectKind.FOUNDRY_PROJECT: resync_foundry_projects,
    ObjectKind.AGENT: resync_foundry_agents,
    ObjectKind.AGENT_VERSION: resync_foundry_agent_versions,
    ObjectKind.MODEL_DEPLOYMENT: resync_foundry_model_deployments,
    ObjectKind.CONVERSATION: resync_foundry_conversations,
    ObjectKind.RESPONSE: resync_foundry_responses,
    ObjectKind.MEMORY_STORE: resync_foundry_memory_stores,
}
