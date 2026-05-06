from typing import Literal, NotRequired, Required, TypedDict

ClaudeUsageGroupBy = Literal[
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


class ClaudeBaseReportOptions(TypedDict):
    starting_at: Required[str]
    limit: Required[int]


class ListClaudeUsageReportOptions(ClaudeBaseReportOptions):
    bucket_width: NotRequired[Literal["1m", "1h", "1d"]]
    group_by: NotRequired[list[ClaudeUsageGroupBy]]


class ListClaudeCostReportOptions(ClaudeBaseReportOptions):
    bucket_width: NotRequired[Literal["1d"]]


class ListClaudeCodeAnalyticsOptions(TypedDict):
    starting_at: Required[str]
    limit: Required[int]
