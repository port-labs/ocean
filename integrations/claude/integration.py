from typing import Literal
from enum import StrEnum

from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import Selector

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig


class ObjectKind(StrEnum):
    CLAUDE_USAGE_RECORD = "claude-usage-record"
    CLAUDE_COST_RECORD = "claude-cost-record"
    CLAUDE_CODE_ANALYTICS = "claude-code-analytics"


class ClaudeUsageSelector(Selector):
    starting_date: str | None = Field(
        alias="startingDate",
        default=None,
        title="Starting Date",
        description="ISO-8601 UTC start date used as the starting_at query parameter. Defaults to today if not set.",
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    bucket_width: Literal["1m", "1h", "1d"] = Field(
        alias="bucketWidth",
        default="1d",
        title="Bucket Width",
        description="Time bucket granularity for usage reports.",
    )
    group_by: list[
        Literal[
            "api_key_id",
            "workspace_id",
            "context_window",
            "speed",
            "inference_geo",
            "account_id",
            "service_account_id",
            "model",
            "service_tier",
        ]
    ] = Field(
        alias="groupBy",
        default_factory=list,
        title="Group By",
        description="Optional dimensions for grouping usage metrics.",
    )


class ClaudeCostSelector(Selector):
    starting_date: str | None = Field(
        alias="startingDate",
        default=None,
        title="Starting Date",
        description="ISO-8601 UTC start date used as the starting_at query parameter. Defaults to today if not set.",
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    bucket_width: Literal["1d"] = Field(
        alias="bucketWidth",
        default="1d",
        title="Bucket Width",
        description="Time bucket granularity for cost reports.",
    )


class ClaudeCodeAnalyticsSelector(Selector):
    starting_date: str | None = Field(
        alias="startingDate",
        default=None,
        title="Starting Date",
        description="Start date for Claude Code analytics in YYYY-MM-DD format. Defaults to today if not set.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )


class ClaudeUsageRecordResourceConfig(ResourceConfig):
    kind: Literal["claude-usage-record"] = Field(
        description="Claude usage record resource kind",
        title="Claude Usage Record",
    )
    selector: ClaudeUsageSelector


class ClaudeCostRecordResourceConfig(ResourceConfig):
    kind: Literal["claude-cost-record"] = Field(
        description="Claude cost record resource kind",
        title="Claude Cost Record",
    )
    selector: ClaudeCostSelector


class ClaudeCodeAnalyticsResourceConfig(ResourceConfig):
    kind: Literal["claude-code-analytics"] = Field(
        description="Claude code analytics resource kind",
        title="Claude Code Analytics",
    )
    selector: ClaudeCodeAnalyticsSelector


class ClaudePortAppConfig(PortAppConfig):
    resources: list[
        ClaudeUsageRecordResourceConfig
        | ClaudeCostRecordResourceConfig
        | ClaudeCodeAnalyticsResourceConfig
    ] = Field(
        description="Resources for claude",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class ClaudeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ClaudePortAppConfig
