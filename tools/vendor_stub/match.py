from __future__ import annotations

import json
import re
from typing import Any

from tools.vendor_stub.models import Registration


def _path_matches(reg: Registration, path: str) -> bool:
    if reg.path is not None and reg.path == path:
        return True
    if reg.path_regex is not None:
        return re.search(reg.path_regex, path) is not None
    return reg.path is None and reg.path_regex is None


def _query_matches(reg: Registration, query: dict[str, str]) -> bool:
    if not reg.query:
        return True
    for key, value in reg.query.items():
        if query.get(key) != str(value):
            return False
    return True


def _headers_match(reg: Registration, headers: dict[str, str]) -> bool:
    if not reg.headers:
        return True
    lower = {k.lower(): v for k, v in headers.items()}
    for key, value in reg.headers.items():
        if lower.get(key.lower()) != value:
            return False
    return True


def _body_matches(reg: Registration, body_text: str) -> bool:
    if reg.body_contains is not None and reg.body_contains not in body_text:
        return False

    if reg.body_field:
        try:
            payload = json.loads(body_text) if body_text else {}
        except json.JSONDecodeError:
            return False
        for key, value in reg.body_field.items():
            if payload.get(key) != value:
                return False
    return True


def condition_failures(
    reg: Registration,
    *,
    method: str,
    path: str,
    query: dict[str, str],
    headers: dict[str, str],
    body_text: str,
) -> list[str]:
    """Return names of conditions that failed. Empty list means full match."""
    failed: list[str] = []
    if reg.method and reg.method.upper() != method.upper():
        failed.append("method")
    if (reg.path is not None or reg.path_regex is not None) and not _path_matches(
        reg, path
    ):
        failed.append("path")
    if not _query_matches(reg, query):
        failed.append("query")
    if not _headers_match(reg, headers):
        failed.append("headers")
    if not _body_matches(reg, body_text):
        failed.append("body")
    return failed


def matches(reg: Registration, **kwargs: Any) -> bool:
    return not condition_failures(reg, **kwargs)


def find_best(
    registrations: list[Registration],
    *,
    method: str,
    path: str,
    query: dict[str, str],
    headers: dict[str, str],
    body_text: str,
) -> tuple[Registration | None, list[str]]:
    """Return (matching registration, []) or (None, failures on closest)."""
    full_matches: list[Registration] = []
    closest: Registration | None = None
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
        score = reg.condition_count() - len(failed)
        if score > closest_score:
            closest_score = score
            closest = reg
            closest_failed = failed

    if not full_matches:
        return None, closest_failed if closest else ["no registrations"]

    # priority desc, then insertion order (stable)
    full_matches.sort(key=lambda r: r.priority, reverse=True)
    return full_matches[0], []
