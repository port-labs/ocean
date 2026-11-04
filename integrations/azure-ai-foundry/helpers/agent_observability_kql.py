from __future__ import annotations


def build_agent_observability_query(window_days: int) -> str:
    """Single Kusto query: aggregate Foundry agent metrics grouped by AgentId."""
    days = max(1, min(window_days, 90))
    return f"""
let lookback = {days}d;
AzureMetrics
| where TimeGenerated > ago(lookback)
| where MetricName in (
    "AgentInputTokens",
    "AgentOutputTokens",
    "AgentResponses",
    "AgentRuns",
    "AgentToolCalls",
    "AgentModelEstimatedCost"
)
| extend dims = parse_json(tostring(Dimensions))
| extend AgentId = coalesce(
    tostring(dims.AgentId),
    tostring(dims.agentId),
    tostring(dims.AgentName),
    tostring(dims.agentName)
)
| where isnotempty(AgentId)
| summarize
    metrics_input_tokens = sumif(Total, MetricName == "AgentInputTokens"),
    metrics_output_tokens = sumif(Total, MetricName == "AgentOutputTokens"),
    metrics_responses = sumif(Total, MetricName == "AgentResponses"),
    metrics_runs = sumif(Total, MetricName == "AgentRuns"),
    metrics_tool_calls = sumif(Total, MetricName == "AgentToolCalls"),
    metrics_estimated_cost_usd = sumif(Total, MetricName == "AgentModelEstimatedCost")
  by AgentId
| extend metrics_window_days = {days}
""".strip()
