from typing import Literal
from enum import StrEnum

from pydantic import Field, root_validator
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
    CLAUDE_USER_ACTIVITY = "claude-user-activity"
    CLAUDE_ACTIVITY_SUMMARY = "claude-activity-summary"
    CLAUDE_USER_USAGE_REPORT = "claude-user-usage-report"
    CLAUDE_USER_COST_REPORT = "claude-user-cost-report"


class ClaudeUsageSelector(Selector):
    starting_date: str = Field(
        alias="startingDate",
        default="2026-01-01T00:00:00Z",
        title="Starting Date",
        description="ISO-8601 UTC start date used as the starting_at query parameter.",
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
            "product",
            "model",
            "context_window",
            "speed",
            "inference_geo",
        ]
    ] = Field(
        alias="groupBy",
        default_factory=list,
        title="Group By",
        description="Optional dimensions for grouping usage metrics.",
    )


class ClaudeCostSelector(Selector):
    starting_date: str = Field(
        alias="startingDate",
        default="2026-01-01T00:00:00Z",
        title="Starting Date",
        description="ISO-8601 UTC start date used as the starting_at query parameter.",
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    bucket_width: Literal["1d"] = Field(
        alias="bucketWidth",
        default="1d",
        title="Bucket Width",
        description="Time bucket granularity for cost reports.",
    )
    group_by: list[
        Literal[
            "product",
            "model",
            "context_window",
            "speed",
            "inference_geo",
            "cost_type",
            "token_type",
        ]
    ] = Field(
        alias="groupBy",
        default_factory=list,
        title="Group By",
        description="Optional dimensions for grouping cost metrics.",
    )


class ClaudeUserActivitySelector(Selector):
    starting_date: str | None = Field(
        alias="startingDate",
        default=None,
        title="Starting Date",
        description=(
            "Start date in YYYY-MM-DD format. The integration calls the API once for "
            "each day from this date to today. Mutually exclusive with timeFrame."
        ),
        pattern=r"^\d{4}-\d{2}-\d{2}$",
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


class ClaudeActivitySummarySelector(Selector):
    starting_date: str = Field(
        alias="startingDate",
        default="2026-01-01",
        title="Starting Date",
        description="Start date in YYYY-MM-DD format (inclusive). Maximum 31-day range.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    ending_date: str | None = Field(
        alias="endingDate",
        default=None,
        title="Ending Date",
        description="End date in YYYY-MM-DD format (exclusive). Defaults to today if not set.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )


class ClaudeUserUsageReportSelector(Selector):
    starting_date: str = Field(
        alias="startingDate",
        default="2026-01-01T00:00:00Z",
        title="Starting Date",
        description="RFC 3339 start date for per-user token usage data.",
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    ending_date: str | None = Field(
        alias="endingDate",
        default=None,
        title="Ending Date",
        description="RFC 3339 end date (exclusive). Maximum 31-day range.",
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    group_by: list[
        Literal[
            "product",
            "model",
            "context_window",
            "speed",
            "inference_geo",
        ]
    ] = Field(
        alias="groupBy",
        default_factory=list,
        title="Group By",
        description="Optional dimensions for grouping per-user usage metrics.",
    )
    order_by: Literal[
        "total_tokens", "output_tokens", "uncached_input_tokens"
    ] = Field(
        alias="orderBy",
        default="total_tokens",
        title="Order By",
        description="Field to sort results by (descending).",
    )


class ClaudeUserCostReportSelector(Selector):
    starting_date: str = Field(
        alias="startingDate",
        default="2026-01-01T00:00:00Z",
        title="Starting Date",
        description="RFC 3339 start date for per-user cost data.",
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    ending_date: str | None = Field(
        alias="endingDate",
        default=None,
        title="Ending Date",
        description="RFC 3339 end date (exclusive). Maximum 31-day range.",
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    )
    group_by: list[
        Literal[
            "product",
            "model",
            "context_window",
            "speed",
            "inference_geo",
            "cost_type",
            "token_type",
        ]
    ] = Field(
        alias="groupBy",
        default_factory=list,
        title="Group By",
        description="Optional dimensions for grouping per-user cost metrics.",
    )
    order_by: Literal["amount", "list_amount"] = Field(
        alias="orderBy",
        default="amount",
        title="Order By",
        description="Field to sort results by (descending).",
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


class ClaudeUserActivityResourceConfig(ResourceConfig):
    kind: Literal["claude-user-activity"] = Field(
        description="Claude per-user daily activity resource kind",
        title="Claude User Activity",
    )
    selector: ClaudeUserActivitySelector


class ClaudeActivitySummaryResourceConfig(ResourceConfig):
    kind: Literal["claude-activity-summary"] = Field(
        description="Claude organisation-level activity summary resource kind",
        title="Claude Activity Summary",
    )
    selector: ClaudeActivitySummarySelector


class ClaudeUserUsageReportResourceConfig(ResourceConfig):
    kind: Literal["claude-user-usage-report"] = Field(
        description="Claude per-user token usage report resource kind",
        title="Claude User Usage Report",
    )
    selector: ClaudeUserUsageReportSelector


class ClaudeUserCostReportResourceConfig(ResourceConfig):
    kind: Literal["claude-user-cost-report"] = Field(
        description="Claude per-user cost report resource kind",
        title="Claude User Cost Report",
    )
    selector: ClaudeUserCostReportSelector


class ClaudePortAppConfig(PortAppConfig):
    resources: list[
        ClaudeUsageRecordResourceConfig
        | ClaudeCostRecordResourceConfig
        | ClaudeUserActivityResourceConfig
        | ClaudeActivitySummaryResourceConfig
        | ClaudeUserUsageReportResourceConfig
        | ClaudeUserCostReportResourceConfig
    ] = Field(
        description="Resources for claude",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class ClaudeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ClaudePortAppConfig
