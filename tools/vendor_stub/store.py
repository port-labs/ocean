from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_registrations: list[dict[str, Any]] = []
_call_log: list[dict[str, Any]] = []
_unmatched: list[dict[str, Any]] = []
# per-registration index into a times/response sequence
_sequence_cursors: dict[str, int] = {}


def reset() -> None:
    with _lock:
        _registrations.clear()
        _call_log.clear()
        _unmatched.clear()
        _sequence_cursors.clear()


def add_registration(reg: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        if "id" not in reg:
            reg["id"] = f"reg-{len(_registrations) + 1}"
        _registrations.append(reg)
        _sequence_cursors[reg["id"]] = 0
        return reg


def list_registrations() -> list[dict[str, Any]]:
    with _lock:
        return list(_registrations)


def log_call(entry: dict[str, Any]) -> None:
    with _lock:
        _call_log.append(entry)


def log_unmatched(entry: dict[str, Any]) -> None:
    with _lock:
        _unmatched.append(entry)


def get_unmatched() -> list[dict[str, Any]]:
    with _lock:
        return list(_unmatched)


def get_call_log() -> list[dict[str, Any]]:
    with _lock:
        return list(_call_log)


def next_sequence_response(
    reg_id: str, responses: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Advance through a response sequence. Returns None when exhausted."""
    with _lock:
        idx = _sequence_cursors.get(reg_id, 0)
        if idx >= len(responses):
            return None
        _sequence_cursors[reg_id] = idx + 1
        return responses[idx]


def bump_times_remaining(reg: dict[str, Any]) -> bool:
    """If times is an int, decrement and return False when exhausted before this serve."""
    with _lock:
        times = reg.get("times")
        if not isinstance(times, int):
            return True
        if times <= 0:
            return False
        reg["times"] = times - 1
        return True
