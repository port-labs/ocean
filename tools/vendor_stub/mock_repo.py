from __future__ import annotations

import threading
from typing import Any, ClassVar


class MockRepo:
    """In-memory registration / call state for the vendor stub."""

    _lock: ClassVar[threading.Lock] = threading.Lock()
    _registrations: ClassVar[list[dict[str, Any]]] = []
    _call_log: ClassVar[list[dict[str, Any]]] = []
    _unmatched: ClassVar[list[dict[str, Any]]] = []
    # per-registration index into a times/response sequence
    _sequence_cursors: ClassVar[dict[str, int]] = {}

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._registrations.clear()
            cls._call_log.clear()
            cls._unmatched.clear()
            cls._sequence_cursors.clear()

    @classmethod
    def add_registration(cls, reg: dict[str, Any]) -> dict[str, Any]:
        with cls._lock:
            if "id" not in reg:
                reg["id"] = f"reg-{len(cls._registrations) + 1}"
            cls._registrations.append(reg)
            cls._sequence_cursors[reg["id"]] = 0
            return reg

    @classmethod
    def list_registrations(cls) -> list[dict[str, Any]]:
        with cls._lock:
            return list(cls._registrations)

    @classmethod
    def log_call(cls, entry: dict[str, Any]) -> None:
        with cls._lock:
            cls._call_log.append(entry)

    @classmethod
    def log_unmatched(cls, entry: dict[str, Any]) -> None:
        with cls._lock:
            cls._unmatched.append(entry)

    @classmethod
    def get_unmatched(cls) -> list[dict[str, Any]]:
        with cls._lock:
            return list(cls._unmatched)

    @classmethod
    def get_call_log(cls) -> list[dict[str, Any]]:
        with cls._lock:
            return list(cls._call_log)

    @classmethod
    def next_sequence_response(
        cls, reg_id: str, responses: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Advance through a response sequence. Returns None when exhausted."""
        with cls._lock:
            idx = cls._sequence_cursors.get(reg_id, 0)
            if idx >= len(responses):
                return None
            cls._sequence_cursors[reg_id] = idx + 1
            return responses[idx]

    @classmethod
    def bump_times_remaining(cls, reg: dict[str, Any]) -> bool:
        """If times is an int, decrement and return False when exhausted before this serve."""
        with cls._lock:
            times = reg.get("times")
            if not isinstance(times, int):
                return True
            if times <= 0:
                return False
            reg["times"] = times - 1
            return True
