from __future__ import annotations

import threading
from typing import Any, ClassVar

from tools.vendor_stub.models import MockResponse, Registration


class MockRepo:
    """In-memory registration / call state for the vendor stub."""

    _lock: ClassVar[threading.Lock] = threading.Lock()
    _registrations: ClassVar[list[Registration]] = []
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
    def add_registration(cls, reg: Registration) -> Registration:
        with cls._lock:
            if not reg.id:
                reg.id = f"reg-{len(cls._registrations) + 1}"
            cls._registrations.append(reg)
            cls._sequence_cursors[reg.id] = 0
            return reg

    @classmethod
    def list_registrations(cls) -> list[Registration]:
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
    def next_sequence_response(cls, reg: Registration) -> MockResponse | None:
        """Advance through a response sequence. Returns None when exhausted."""
        with cls._lock:
            if not isinstance(reg.times, list) or not reg.id:
                return None
            idx = cls._sequence_cursors.get(reg.id, 0)
            if idx >= len(reg.times):
                return None
            cls._sequence_cursors[reg.id] = idx + 1
            return reg.times[idx]

    @classmethod
    def bump_times_remaining(cls, reg: Registration) -> bool:
        """If times is an int, decrement and return False when exhausted before this serve."""
        with cls._lock:
            if not isinstance(reg.times, int):
                return True
            if reg.times <= 0:
                return False
            reg.times -= 1
            return True
