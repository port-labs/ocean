from typing import Literal

from pydantic.v1 import Field

from langfuse.helpers.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class PromptSelector(Selector):
    label: str | None = Field(
        default=None,
        description="Only sync prompts that have this deployment label.",
    )
    tag: str | None = Field(
        default=None,
        description="Only sync prompts that have this tag.",
    )


class PromptResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PROMPT] = Field(description="Langfuse prompt")
    selector: PromptSelector = Field(
        title="Prompt Selector",
        description="Optional label/tag filters for Langfuse prompts.",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PROJECT] = Field(description="Langfuse project")


class DatasetResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DATASET] = Field(description="Langfuse dataset")


class ModelResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.MODEL] = Field(description="Langfuse model definition")


class SessionSelector(Selector):
    lookback_days: int = Field(
        default=7,
        ge=1,
        description="How many days of observations to scan when reconstructing sessions.",
    )


class SessionResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SESSION] = Field(description="Langfuse session")
    selector: SessionSelector = Field(
        default_factory=SessionSelector,
        title="Session Selector",
        description="Lookback window for reconstructing sessions from observations.",
    )


class LangfusePortAppConfig(PortAppConfig):
    resources: list[
        ProjectResourceConfig
        | PromptResourceConfig
        | DatasetResourceConfig
        | ModelResourceConfig
        | SessionResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class LangfuseIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = LangfusePortAppConfig
