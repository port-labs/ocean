from typing import Literal, NotRequired, Required, TypedDict

# Claude Platform — message usage & cost reports

ClaudePlatformUsageGroupBy = Literal[
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


class PlatformBaseReportOptions(TypedDict):
    starting_at: Required[str]
    limit: Required[int]


class ListPlatformUsageReportOptions(PlatformBaseReportOptions):
    bucket_width: NotRequired[Literal["1m", "1h", "1d"]]
    group_by: NotRequired[list[ClaudePlatformUsageGroupBy]]


class ListPlatformCostReportOptions(PlatformBaseReportOptions):
    bucket_width: NotRequired[Literal["1d"]]


class ListPlatformCodeAnalyticsOptions(TypedDict):
    starting_at: Required[str]
    limit: Required[int]


# Claude AI / Enterprise — per-user analytics

ClaudeAIProduct = Literal[
    "chat",
    "claude_code",
    "cowork",
    "office_agent",
    "claude_in_chrome",
    "claude_design",
]

ClaudeAIGroupBy = Literal[
    "product",
    "model",
    "context_window",
    "inference_geo",
    "speed",
]

ClaudeAIContextWindow = Literal["0-200k", "200k-1M"]
ClaudeAIInferenceGeo = Literal["global", "us", "not_available"]
ClaudeAISpeed = Literal["fast", "standard"]


class ListUserActivityOptions(TypedDict):
    """Query options for the per-day users analytics endpoint.

    The users endpoint only accepts date and limit.
    """

    date: Required[str]
    limit: Required[int]


class ListUserReportOptions(TypedDict):
    """Shared query options for the user usage and cost report endpoints."""

    starting_at: Required[str]
    ending_at: Required[str]
    limit: Required[int]
    exclude_deleted_users: NotRequired[bool]
    products: NotRequired[list[ClaudeAIProduct]]
    models: NotRequired[list[str]]
    group_by: NotRequired[list[ClaudeAIGroupBy]]
    context_windows: NotRequired[list[ClaudeAIContextWindow]]
    inference_geos: NotRequired[list[ClaudeAIInferenceGeo]]
    speeds: NotRequired[list[ClaudeAISpeed]]
