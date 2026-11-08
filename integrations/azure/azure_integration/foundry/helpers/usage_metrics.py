from __future__ import annotations

from typing import Any


def _as_int(value: Any) -> int:
    return int(value)


def merge_usage_into_row(row: dict[str, Any], usage: dict[str, Any]) -> None:
    prompt = usage.get("prompt_tokens")
    if prompt is None:
        prompt = usage.get("input_tokens")
    completion = usage.get("completion_tokens")
    if completion is None:
        completion = usage.get("output_tokens")
    total = usage.get("total_tokens")
    if prompt is not None:
        row["prompt_tokens"] = _as_int(prompt)
    if completion is not None:
        row["completion_tokens"] = _as_int(completion)
    if total is not None:
        row["total_tokens"] = _as_int(total)
    elif prompt is not None and completion is not None:
        row["total_tokens"] = _as_int(prompt) + _as_int(completion)


def add_usage_rows(
    totals: dict[str, int],
    usage: dict[str, Any] | None,
) -> None:
    if not isinstance(usage, dict):
        return
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens")
    completion = usage.get("completion_tokens") or usage.get("output_tokens")
    total = usage.get("total_tokens")
    if prompt is not None:
        totals["prompt_tokens"] = totals.get("prompt_tokens", 0) + _as_int(prompt)
    if completion is not None:
        totals["completion_tokens"] = totals.get("completion_tokens", 0) + _as_int(
            completion
        )
    if total is not None:
        totals["total_tokens"] = totals.get("total_tokens", 0) + _as_int(total)
    elif prompt is not None and completion is not None:
        totals["total_tokens"] = (
            totals.get("total_tokens", 0) + _as_int(prompt) + _as_int(completion)
        )


def count_tool_calls_in_response(response: dict[str, Any]) -> int:
    output = response.get("output")
    if not isinstance(output, list):
        return 0
    tool_types = {
        "function_call",
        "mcp_call",
        "tool_call",
        "code_interpreter_call",
        "file_search_call",
        "web_search_call",
    }
    return sum(
        1
        for item in output
        if isinstance(item, dict) and str(item.get("type") or "") in tool_types
    )
