from github.helpers.api_trace_logging import (
    extract_response_items,
    format_curl_request,
    format_response_summary,
)


def test_format_curl_request_includes_query_params() -> None:
    curl = format_curl_request(
        "GET",
        "https://api.github.com/repos/org/repo/issues",
        {"since": "2026-01-01T00:00:00Z", "state": "all"},
    )
    assert "curl -sS -X GET" in curl
    assert "since=2026-01-01" in curl
    assert "state=all" in curl


def test_format_response_summary_lists_preview() -> None:
    body = [
        {"id": 1, "number": 42, "title": "Bug", "state": "open"},
        {"id": 2, "number": 43, "title": "Feat", "state": "closed"},
    ]
    summary = format_response_summary(body)
    assert "2 item(s)" in summary
    assert "number" in summary


def test_extract_response_items_workflow_runs() -> None:
    body = {"workflow_runs": [{"id": 99, "name": "CI"}]}
    assert len(extract_response_items(body)) == 1
