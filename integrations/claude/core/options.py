from typing import Literal, NotRequired, Required, TypedDict

ClaudeUsageGroupBy = Literal[
    "product",
    "model",
    "context_window",
    "speed",
    "inference_geo",
]

ClaudeCostGroupBy = Literal[
    "product",
    "model",
    "context_window",
    "speed",
    "inference_geo",
    "cost_type",
    "token_type",
]


class ClaudeBaseReportOptions(TypedDict):
    starting_at: Required[str]
    limit: Required[int]


class ListClaudeUsageReportOptions(ClaudeBaseReportOptions):
    bucket_width: NotRequired[Literal["1m", "1h", "1d"]]
    group_by: NotRequired[list[ClaudeUsageGroupBy]]


class ListClaudeCostReportOptions(ClaudeBaseReportOptions):
    bucket_width: NotRequired[Literal["1d"]]
    group_by: NotRequired[list[ClaudeCostGroupBy]]


class ListClaudeUserActivityOptions(TypedDict):
    date: Required[str]
    limit: Required[int]


class ListClaudeActivitySummaryOptions(TypedDict):
    starting_date: Required[str]
    ending_date: NotRequired[str]


class ListClaudeUserUsageReportOptions(ClaudeBaseReportOptions):
    ending_at: NotRequired[str]
    group_by: NotRequired[list[ClaudeUsageGroupBy]]
    order_by: NotRequired[
        Literal["total_tokens", "output_tokens", "uncached_input_tokens"]
    ]


class ListClaudeUserCostReportOptions(ClaudeBaseReportOptions):
    ending_at: NotRequired[str]
    group_by: NotRequired[list[ClaudeCostGroupBy]]
    order_by: NotRequired[Literal["amount", "list_amount"]]
