from __future__ import annotations

import json
import re
from typing import Any


def _path_matches(condition: dict[str, Any], path: str) -> bool:
    exact = condition.get("path")
    if exact is not None and exact == path:
        return True
    pattern = condition.get("path_regex")
    if pattern is not None:
        return re.search(pattern, path) is not None
    # no path condition set
    return exact is None and pattern is None


def _query_matches(condition: dict[str, Any], query: dict[str, str]) -> bool:
    expected = condition.get("query")
    if not expected:
        return True
    for key, value in expected.items():
        if query.get(key) != str(value):
            return False
    return True


def _headers_match(condition: dict[str, Any], headers: dict[str, str]) -> bool:
    expected = condition.get("headers")
    if not expected:
        return True
    lower = {k.lower(): v for k, v in headers.items()}
    for key, value in expected.items():
        if lower.get(key.lower()) != value:
            return False
    return True


def _body_matches(condition: dict[str, Any], body_text: str) -> bool:
    substring = condition.get("body_contains")
    if substring is not None and substring not in body_text:
        return False

    body_field = condition.get("body_field")
    if body_field:
        try:
            payload = json.loads(body_text) if body_text else {}
        except json.JSONDecodeError:
            return False
        for key, value in body_field.items():
            if payload.get(key) != value:
                return False
    return True


def condition_failures(
    reg: dict[str, Any],
    *,
    method: str,
    path: str,
    query: dict[str, str],
    headers: dict[str, str],
    body_text: str,
) -> list[str]:
    """Return names of conditions that failed. Empty list means full match."""
    failed: list[str] = []
    if reg.get("method") and reg["method"].upper() != method.upper():
        failed.append("method")
    if (
        reg.get("path") is not None or reg.get("path_regex") is not None
    ) and not _path_matches(reg, path):
        failed.append("path")
    if not _query_matches(reg, query):
        failed.append("query")
    if not _headers_match(reg, headers):
        failed.append("headers")
    if not _body_matches(reg, body_text):
        failed.append("body")
    return failed


def matches(reg: dict[str, Any], **kwargs: Any) -> bool:
    return not condition_failures(reg, **kwargs)


def find_best(
    registrations: list[dict[str, Any]],
    *,
    method: str,
    path: str,
    query: dict[str, str],
    headers: dict[str, str],
    body_text: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (matching registration, []) or (None, failures on closest)."""
    full_matches: list[dict[str, Any]] = []
    closest: dict[str, Any] | None = None
    closest_failed: list[str] = []
    closest_score = -1

    for reg in registrations:
        failed = condition_failures(
            reg,
            method=method,
            path=path,
            query=query,
            headers=headers,
            body_text=body_text,
        )
        if not failed:
            full_matches.append(reg)
            continue
        # score = how many conditions were set and passed
        set_count = sum(
            1
            for key in (
                "method",
                "path",
                "path_regex",
                "query",
                "headers",
                "body_contains",
                "body_field",
            )
            if reg.get(key) is not None
        )
        score = set_count - len(failed)
        if score > closest_score:
            closest_score = score
            closest = reg
            closest_failed = failed

    if not full_matches:
        return None, closest_failed if closest else ["no registrations"]

    # priority desc, then insertion order (stable)
    full_matches.sort(key=lambda r: r.get("priority", 0), reverse=True)
    return full_matches[0], []
