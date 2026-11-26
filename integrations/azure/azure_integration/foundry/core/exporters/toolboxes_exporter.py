from __future__ import annotations

from typing import Any

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.core.exporters.base import FoundryExporter
from azure_integration.foundry.core.options import ListToolboxesOptions, SingleToolboxOptions
from azure_integration.foundry.foundry_incremental import TOOLBOX_INCREMENTAL
from azure_integration.foundry.helpers.a2a import (
    a2a_connection_ids_from_tools,
    parse_foundry_a2a_url,
    skill_names_from_refs,
)
from azure_integration.foundry.helpers.toolbox import mcp_urls_from_tools
from azure_integration.foundry.helpers.utils import (
    build_foundry_url,
    enrich_with_project,
)

TOOLBOXES_HEADERS = {"Foundry-Features": "Toolboxes=V1Preview"}


class ToolboxLatestVersion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skills: list[Any] = Field(default_factory=list)
    tools: list[Any] = Field(default_factory=list)

    @field_validator("skills", "tools", mode="before")
    @classmethod
    def _coerce_list(cls, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []


class ToolboxVersions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    latest: ToolboxLatestVersion | None = None

    @field_validator("latest", mode="before")
    @classmethod
    def _coerce_latest(cls, value: Any) -> Any:
        return value if isinstance(value, dict) else None


class ToolboxPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    versions: ToolboxVersions | None = None

    @field_validator("versions", mode="before")
    @classmethod
    def _coerce_versions(cls, value: Any) -> Any:
        return value if isinstance(value, dict) else None


class ConnectionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target: str = ""


class ToolboxesExporter(FoundryExporter[ListToolboxesOptions, SingleToolboxOptions]):
    async def get_resource(
        self, options: SingleToolboxOptions
    ) -> dict[str, Any] | None:
        try:
            detail = await self.client.send_api_request(
                build_foundry_url(
                    options.project_endpoint, f"toolboxes/{options.toolbox_name}"
                ),
                extra_headers=TOOLBOXES_HEADERS,
            )
        except FoundryApiError as error:
            if error.status_code == 404:
                return None
            raise
        return detail if isinstance(detail, dict) and detail else None

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListToolboxesOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        cursor = active_incremental_cursor()
        params = TOOLBOX_INCREMENTAL.merge_params({}, cursor)

        async for page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "toolboxes",
                params=params,
                extra_headers=TOOLBOXES_HEADERS,
            ),
            cursor=cursor,
            strategy=TOOLBOX_INCREMENTAL,
        ):
            batch: list[dict[str, Any]] = []
            for item in page:
                name = item.get("name") or item.get("id")
                if name:
                    loaded = await self.get_resource(
                        SingleToolboxOptions(
                            project_endpoint=project_endpoint,
                            project_id=project_id,
                            toolbox_name=str(name),
                        )
                    )
                    toolbox = {**item, **loaded} if loaded else dict(item)
                else:
                    toolbox = dict(item)
                toolbox = await self._enrich_toolbox(
                    toolbox, project_endpoint=project_endpoint
                )
                batch.append(
                    enrich_with_project(
                        toolbox,
                        project_endpoint=project_endpoint,
                        project_id=project_id,
                    )
                )
            yield batch

    async def _enrich_toolbox(
        self,
        toolbox: dict[str, Any],
        *,
        project_endpoint: str,
    ) -> dict[str, Any]:
        enriched = dict(toolbox)
        try:
            parsed = ToolboxPayload.model_validate(toolbox)
        except ValidationError:
            return {
                **enriched,
                "__skillNames": [],
                "__mcpUrls": [],
                "__a2aSubagents": [],
            }

        latest = parsed.versions.latest if parsed.versions else None
        if latest is None:
            return {
                **enriched,
                "__skillNames": [],
                "__mcpUrls": [],
                "__a2aSubagents": [],
            }

        enriched["__skillNames"] = skill_names_from_refs(latest.skills)
        enriched["__mcpUrls"] = mcp_urls_from_tools(latest.tools)
        enriched["__a2aSubagents"] = await self._a2a_subagents(
            project_endpoint, latest.tools
        )
        return enriched

    async def _a2a_subagents(
        self,
        project_endpoint: str,
        tools: list[Any],
    ) -> list[dict[str, Any]]:
        subagents: list[dict[str, Any]] = []
        for conn_name in a2a_connection_ids_from_tools(tools):
            try:
                payload = await self.client.send_api_request(
                    build_foundry_url(project_endpoint, f"connections/{conn_name}"),
                    extra_headers=TOOLBOXES_HEADERS,
                )
            except FoundryApiError as error:
                if error.status_code == 404:
                    subagents.append({"connectionName": conn_name})
                    continue
                raise
            if not isinstance(payload, dict) or not payload:
                subagents.append({"connectionName": conn_name})
                continue
            connection = ConnectionPayload.model_validate(payload)
            entry: dict[str, Any] = {
                "connectionName": conn_name,
                "target": connection.target,
            }
            project_name, agent_name = parse_foundry_a2a_url(connection.target)
            if project_name:
                entry["projectName"] = project_name
            if agent_name:
                entry["agentName"] = agent_name
            subagents.append(entry)
        return subagents
