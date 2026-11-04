from clients.agent_observability_client import (
    AgentObservabilityTotals,
    _merge_monitor_payload,
    _parse_log_analytics_table,
    enrich_agent_with_observability,
)
from helpers.agent_observability_kql import build_agent_observability_query
from helpers.project_scope import project_name_from_endpoint


def test_build_agent_observability_query_groups_by_agent_id() -> None:
    query = build_agent_observability_query(30)
    assert "by AgentId" in query
    assert "metrics_input_tokens" in query
    assert "let lookback = 30d" in query


def test_project_name_from_endpoint() -> None:
    assert (
        project_name_from_endpoint(
            "https://acct.services.ai.azure.com/api/projects/proj-default"
        )
        == "proj-default"
    )


def test_parse_log_analytics_table() -> None:
    payload = {
        "tables": [
            {
                "columns": [
                    {"name": "AgentId", "type": "string"},
                    {"name": "metrics_input_tokens", "type": "real"},
                    {"name": "metrics_runs", "type": "real"},
                ],
                "rows": [["agent-a", 100.0, 5.0]],
            }
        ]
    }
    result = _parse_log_analytics_table(payload, window_days=7)
    assert "agent-a" in result
    assert result["agent-a"].metrics_input_tokens == 100.0
    assert result["agent-a"].metrics_runs == 5.0
    assert result["agent-a"].metrics_window_days == 7


def test_merge_monitor_payload() -> None:
    totals: dict[str, AgentObservabilityTotals] = {}
    payload = {
        "value": [
            {
                "name": {"value": "AgentInputTokens"},
                "timeseries": [
                    {
                        "metadatavalues": [
                            {"name": {"value": "AgentId"}, "value": "my-agent"}
                        ],
                        "data": [{"total": 10.0}, {"total": 5.0}],
                    }
                ],
            }
        ]
    }
    _merge_monitor_payload(payload, totals, window_days=30)
    assert totals["my-agent"].metrics_input_tokens == 15.0


def test_enrich_agent_with_observability() -> None:
    metrics = {
        "demo-agent": AgentObservabilityTotals(
            metrics_input_tokens=42,
            metrics_window_days=30,
        )
    }
    enriched = enrich_agent_with_observability(
        {"id": "demo-agent", "name": "Demo"}, metrics
    )
    assert enriched["metrics_input_tokens"] == 42
    assert enriched["metrics_window_days"] == 30
    assert "metrics_as_of" in enriched
