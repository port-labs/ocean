from enum import StrEnum
from typing import Literal

from pydantic import Field, root_validator
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

# Default start for the Claude Platform usage/cost reports. This is a deliberate
# Platform default and is intentionally independent of the Claude AI (Enterprise) min date.
PLATFORM_DEFAULT_STARTING_DATE = "2025-01-01T00:00:00Z"


class ObjectKind(StrEnum):
    # Claude Platform (api:admin scope)
    CLAUDE_PLATFORM_USAGE_RECORD = "claude-platform-usage-record"
    CLAUDE_PLATFORM_COST_RECORD = "claude-platform-cost-record"
    CLAUDE_PLATFORM_CODE_ANALYTICS = "claude-platform-code-analytics"
    # Claude AI / Enterprise (read:analytics scope)
    CLAUDE_AI_USER_ACTIVITY = "claude-ai-user-activity"
    CLAUDE_AI_USER_USAGE = "claude-ai-user-usage"
    CLAUDE_AI_USER_COST = "claude-ai-user-cost"
    # Deprecated legacy kinds, kept for backwards compatibility. They are
    # aliases of the equivalent claude-platform-* kinds above.
    CLAUDE_USAGE_RECORD = "claude-usage-record"
    CLAUDE_COST_RECORD = "claude-cost-record"
    CLAUDE_CODE_ANALYTICS = "claude-code-analytics"


# Claude Platform selectors


class ClaudePlatformUsageSelector(Selector):
    starting_date: str = Field(
        alias="startingDate",
        default=PLATFORM_DEFAULT_STARTING_DATE,
        title="Starting Date",
        description=(
            "ISO-8601 UTC start date used as the starting_at query parameter. "
            "Defaults to 2025-01-01."
        ),
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
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


class ClaudePlatformCostSelector(Selector):
    starting_date: str = Field(
        alias="startingDate",
        default=PLATFORM_DEFAULT_STARTING_DATE,
        title="Starting Date",
        description=(
            "ISO-8601 UTC start date used as the starting_at query parameter. "
            "Defaults to 2025-01-01."
        ),
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    bucket_width: Literal["1d"] = Field(
        alias="bucketWidth",
        default="1d",
        title="Bucket Width",
        description="Time bucket granularity for cost reports.",
    )


class ClaudePlatformCodeAnalyticsSelector(Selector):
    starting_date: str | None = Field(
        alias="startingDate",
        default=None,
        title="Starting Date",
        description=(
            "Start date in YYYY-MM-DD format. The integration calls the API once for "
            "each day from this date to today. Mutually exclusive with timeFrame."
        ),
        regex=r"^\d{4}-\d{2}-\d{2}$",
    )
    time_frame: int | None = Field(
        alias="timeFrame",
        default=None,
        title="Time Frame (days)",
        description=(
            "Number of days to look back from today. The integration calls the API "
            "once per day for each of the last N days. Mutually exclusive with startingDate."
        ),
        gt=0,
    )

    @root_validator
    @classmethod
    def validate_date_config(cls, values: dict[str, object]) -> dict[str, object]:
        has_starting_date = values.get("starting_date") is not None
        has_time_frame = values.get("time_frame") is not None
        if not has_starting_date and not has_time_frame:
            raise ValueError("Either 'startingDate' or 'timeFrame' must be provided")
        if has_starting_date and has_time_frame:
            raise ValueError("'startingDate' and 'timeFrame' are mutually exclusive")
        return values


# Claude AI (Enterprise) selectors


class ClaudeAIUserActivitySelector(Selector):
    starting_date: str | None = Field(
        alias="startingDate",
        default=None,
        title="Starting Date",
        description=(
            "Start date in YYYY-MM-DD format. The integration calls the users API "
            "once per day from this date up to ~3 days ago (the endpoint only "
            "returns data at least 3 days old), clamped to 2026-01-01, the "
            "earliest available data. Mutually exclusive with timeFrame."
        ),
        regex=r"^\d{4}-\d{2}-\d{2}$",
    )
    time_frame: int | None = Field(
        alias="timeFrame",
        default=None,
        title="Time Frame (days)",
        description=(
            "Number of days to look back, ending ~3 days ago (the endpoint only "
            "returns data at least 3 days old). Mutually exclusive with "
            "startingDate. Defaults to 30 days when neither field is set."
        ),
        gt=0,
    )

    @root_validator
    @classmethod
    def validate_date_config(cls, values: dict[str, object]) -> dict[str, object]:
        # Neither field is allowed (a 30-day default is applied downstream); only
        # supplying both is invalid.
        has_starting_date = values.get("starting_date") is not None
        has_time_frame = values.get("time_frame") is not None
        if has_starting_date and has_time_frame:
            raise ValueError("'startingDate' and 'timeFrame' are mutually exclusive")
        return values


class ClaudeAIUserReportSelector(Selector):
    """Shared selector for the user usage and cost report kinds."""

    starting_at: str = Field(
        alias="startingAt",
        default="2026-01-01T00:00:00Z",
        title="Starting At",
        description=(
            "RFC-3339 UTC start of the range (inclusive). Automatically clamped to "
            "the last 31 days and no earlier than 2026-01-01."
        ),
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    ending_at: str | None = Field(
        alias="endingAt",
        default=None,
        title="Ending At",
        description=(
            "RFC-3339 UTC end of the range (exclusive). Defaults to now. The range "
            "spans at most 31 days."
        ),
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    exclude_deleted_users: bool = Field(
        alias="excludeDeletedUsers",
        default=False,
        title="Exclude Deleted Users",
        description="When true, rows for deleted users are omitted.",
    )
    products: list[
        Literal[
            "chat",
            "claude_code",
            "cowork",
            "office_agent",
            "claude_in_chrome",
            "claude_design",
        ]
    ] = Field(
        alias="products",
        default_factory=list,
        title="Products",
        description="Filter to specific seat-based product surfaces.",
    )
    models: list[str] = Field(
        alias="models",
        default_factory=list,
        title="Models",
        description="Filter to specific model names",
    )
    group_by: list[
        Literal["product", "model", "context_window", "inference_geo", "speed"]
    ] = Field(
        alias="groupBy",
        default_factory=list,
        title="Group By",
        description="Break each user's row out by the given dimensions.",
    )
    context_windows: list[Literal["0-200k", "200k-1M"]] = Field(
        alias="contextWindows",
        default_factory=list,
        title="Context Windows",
        description="Filter to specific context-window pricing tiers.",
    )
    inference_geos: list[Literal["global", "us", "not_available"]] = Field(
        alias="inferenceGeos",
        default_factory=list,
        title="Inference Geos",
        description="Filter to specific inference regions.",
    )
    speeds: list[Literal["fast", "standard"]] = Field(
        alias="speeds",
        default_factory=list,
        title="Speeds",
        description="Filter to fast or standard inference mode.",
    )


# Resource configurations


class ClaudePlatformUsageRecordResourceConfig(ResourceConfig):
    # "claude-usage-record" is the deprecated alias kept for backwards
    # compatibility with existing installations.
    kind: Literal["claude-platform-usage-record", "claude-usage-record"] = Field(
        description="Claude Platform usage record resource kind",
        title="Claude Platform Usage Record",
    )
    selector: ClaudePlatformUsageSelector


class ClaudePlatformCostRecordResourceConfig(ResourceConfig):
    # "claude-cost-record" is the deprecated alias kept for backwards
    # compatibility with existing installations.
    kind: Literal["claude-platform-cost-record", "claude-cost-record"] = Field(
        description="Claude Platform cost record resource kind",
        title="Claude Platform Cost Record",
    )
    selector: ClaudePlatformCostSelector


class ClaudePlatformCodeAnalyticsResourceConfig(ResourceConfig):
    # "claude-code-analytics" is the deprecated alias kept for backwards
    # compatibility with existing installations.
    kind: Literal["claude-platform-code-analytics", "claude-code-analytics"] = Field(
        description="Claude Platform code analytics resource kind",
        title="Claude Platform Code Analytics",
    )
    selector: ClaudePlatformCodeAnalyticsSelector


class ClaudeAIUserActivityResourceConfig(ResourceConfig):
    kind: Literal["claude-ai-user-activity"] = Field(
        description="Claude AI per-user activity resource kind",
        title="Claude AI User Activity",
    )
    selector: ClaudeAIUserActivitySelector


class ClaudeAIUserUsageResourceConfig(ResourceConfig):
    kind: Literal["claude-ai-user-usage"] = Field(
        description="Claude AI per-user usage resource kind",
        title="Claude AI User Usage",
    )
    selector: ClaudeAIUserReportSelector


class ClaudeAIUserCostResourceConfig(ResourceConfig):
    kind: Literal["claude-ai-user-cost"] = Field(
        description="Claude AI per-user cost resource kind",
        title="Claude AI User Cost",
    )
    selector: ClaudeAIUserReportSelector


class ClaudePortAppConfig(PortAppConfig):
    resources: list[
        ClaudeAIUserActivityResourceConfig
        | ClaudeAIUserUsageResourceConfig
        | ClaudeAIUserCostResourceConfig
        | ClaudePlatformUsageRecordResourceConfig
        | ClaudePlatformCostRecordResourceConfig
        | ClaudePlatformCodeAnalyticsResourceConfig
    ] = Field(
        description="Resources for claude",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class ClaudeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ClaudePortAppConfig
