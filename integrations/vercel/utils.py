"""
Pure helper functions shared across the Vercel integration.

Keeping these in a separate module allows them to be imported and tested
without triggering Ocean's decorator registrations in main.py.
"""

from __future__ import annotations

from typing import Any


def extract_entity(kind: str, event_payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the primary entity dict out of a Vercel webhook event payload.

    Vercel webhook payloads nest the affected resource under a key that
    matches the resource type, e.g.::

        {
            "type": "deployment.created",
            "payload": {
                "deployment": { ... },
                "project":    { ... }
            }
        }

    When the expected nested key is absent the whole payload is returned
    so callers always receive a usable dict.
    """
    if kind == "deployment":
        return event_payload.get("deployment", event_payload)
    if kind == "project":
        return event_payload.get("project", event_payload)
    if kind == "domain":
        return event_payload.get("domain", event_payload)
    return event_payload
