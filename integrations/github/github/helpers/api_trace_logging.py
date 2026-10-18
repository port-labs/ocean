"""Indicative request/response logging for local incremental/selector debugging."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

from loguru import logger

_TRACE_ENV = "OCEAN__API_TRACE_LOGGING"
_PREVIEW_ITEM_KEYS = (
    "id",
    "node_id",
    "name",
    "number",
    "title",
    "state",
    "status",
    "created_at",
    "updated_at",
    "merged_at",
)
_MAX_PREVIEW_ITEMS = 5


def is_api_trace_enabled() -> bool:
    return os.getenv(_TRACE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def format_curl_request(
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
) -> str:
    parsed = urlparse(url)
    query = dict(params or {})
    if parsed.query:
        for part in parsed.query.split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                query.setdefault(key, value)
    full_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query, doseq=True),
            parsed.fragment,
        )
    )
    return (
        f"curl -sS -X {method.upper()} '{full_url}' "
        "-H 'Authorization: ***' -H 'Accept: application/json'"
    )


def _preview_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    preview = {
        key: item[key]
        for key in _PREVIEW_ITEM_KEYS
        if key in item and item[key] is not None
    }
    if preview:
        return preview
    return {key: item[key] for key in list(item.keys())[:3]}


def extract_response_items(body: Any) -> list[Any]:
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []
    for key in ("items", "workflow_runs", "repositories", "data", "nodes"):
        items = body.get(key)
        if isinstance(items, list):
            return items
    return [body] if body else []


def format_response_summary(body: Any) -> str:
    items = extract_response_items(body)
    preview = [_preview_item(item) for item in items[:_MAX_PREVIEW_ITEMS]]
    if items:
        return f"{len(items)} item(s) | preview={preview}"
    if isinstance(body, dict) and body:
        keys = list(body.keys())[:8]
        return f"0 list items | top-level keys={keys}"
    return f"empty response ({type(body).__name__})"


def log_api_trace(
    method: str,
    url: str,
    params: dict[str, Any] | None,
    response_body: Any,
) -> None:
    if not is_api_trace_enabled():
        return
    logger.info(
        "[API trace] request: {}",
        format_curl_request(method, url, params),
    )
    logger.info(
        "[API trace] response: {}",
        format_response_summary(response_body),
    )
