"""Utility functions and constants for the Vercel integration."""

from typing import Any


class ObjectKind:
    """Constants for Vercel resource kinds."""

    TEAM = "team"
    PROJECT = "project"
    DEPLOYMENT = "deployment"
    DOMAIN = "domain"


def extract_entity(kind: str, event_payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the primary entity dict out of a Vercel webhook payload."""
    if kind == ObjectKind.DEPLOYMENT:
        return event_payload.get("deployment", event_payload)
    if kind == ObjectKind.PROJECT:
        return event_payload.get("project", event_payload)
    if kind == ObjectKind.DOMAIN:
        return event_payload.get("domain", event_payload)
    return event_payload
