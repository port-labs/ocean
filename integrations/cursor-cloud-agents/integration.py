from enum import StrEnum
from typing import Literal

from pydantic.v1 import Field
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class ObjectKind(StrEnum):
    AGENT = "agent"
    RUN = "run"


class AgentSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived agents in the results.",
    )


class RunSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description=(
            "Whether to include runs for archived agents. Controls the agent "
            "list used when fanning out to List Runs (Cursor has no separate "
            "includeArchived flag on List Runs)."
        ),
    )


class AgentResourceConfig(ResourceConfig):
    kind: Literal["agent"] = Field(
        description="Cursor Cloud Agent resource kind (synced via the v1 List Agents API)",
        title="Agent",
    )
    selector: AgentSelector = Field(
        title="Agent Selector",
        description="Selector for the agent resource.",
    )


class RunResourceConfig(ResourceConfig):
    kind: Literal["run"] = Field(
        description="Cursor Cloud Agent run resource kind (synced via the v1 List Runs API, one page per agent)",
        title="Run",
    )
    selector: RunSelector = Field(
        title="Run Selector",
        description="Selector for the run resource.",
    )


class CursorCloudAgentsPortAppConfig(PortAppConfig):
    resources: list[AgentResourceConfig | RunResourceConfig] = Field(
        description="Resources for cursor-cloud-agents",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class CursorCloudAgentsIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CursorCloudAgentsPortAppConfig
