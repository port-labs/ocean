from __future__ import annotations

from typing import Any

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from azure_integration.foundry.core.exporters.base import FoundryExporter
from azure_integration.foundry.core.options import ListToolboxesOptions
from azure_integration.foundry.foundry_incremental import TOOLBOX_INCREMENTAL
from azure_integration.foundry.helpers.a2a import (
    a2a_connection_ids_from_tools,
    parse_foundry_a2a_url,
    skill_names_from_refs,
)
from azure_integration.foundry.helpers.utils import (
    build_foundry_url,
    enrich_with_project,
)

_TOOLBOXES_FEATURE = "Toolboxes=V1Preview"


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


class ToolboxesExporter(FoundryExporter[ListToolboxesOptions]):
    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListToolboxesOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        cursor = active_incremental_cursor()
        params = TOOLBOX_INCREMENTAL.merge_params({}, cursor)
        headers = {"Foundry-Features": _TOOLBOXES_FEATURE}

        async for page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "toolboxes",
                params=params,
                extra_headers=headers,
            ),
            cursor=cursor,
            strategy=TOOLBOX_INCREMENTAL,
        ):
            batch: list[dict[str, Any]] = []
            for item in page:
                toolbox = await self._load_toolbox(
                    project_endpoint, item, headers=headers
                )
                toolbox = await self._enrich_toolbox(
                    toolbox, project_endpoint=project_endpoint, headers=headers
                )
                batch.append(
                    enrich_with_project(
                        toolbox,
                        project_endpoint=project_endpoint,
                        project_id=project_id,
                    )
                )
            yield batch

    async def _load_toolbox(
        self,
        project_endpoint: str,
        item: dict[str, Any],
        *,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        name = item.get("name") or item.get("id")
        if not name:
            return dict(item)
        detail = await self.client.send_api_request(
            build_foundry_url(project_endpoint, f"toolboxes/{name}"),
            extra_headers=headers,
        )
        if isinstance(detail, dict) and detail:
            return {**item, **detail}
        return dict(item)

    async def _enrich_toolbox(
        self,
        toolbox: dict[str, Any],
        *,
        project_endpoint: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        enriched = dict(toolbox)
        try:
            parsed = ToolboxPayload.model_validate(toolbox)
        except ValidationError:
            return {**enriched, "__skillNames": [], "__a2aSubagents": []}

        latest = parsed.versions.latest if parsed.versions else None
        if latest is None:
            return {**enriched, "__skillNames": [], "__a2aSubagents": []}

        enriched["__skillNames"] = skill_names_from_refs(latest.skills)
        enriched["__a2aSubagents"] = await self._a2a_subagents(
            project_endpoint, latest.tools, headers=headers
        )
        return enriched

    async def _a2a_subagents(
        self,
        project_endpoint: str,
        tools: list[Any],
        *,
        headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        subagents: list[dict[str, Any]] = []
        for conn_name in a2a_connection_ids_from_tools(tools):
            payload = await self.client.send_api_request(
                build_foundry_url(project_endpoint, f"connections/{conn_name}"),
                extra_headers=headers,
            )
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
