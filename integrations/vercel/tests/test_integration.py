"""Unit tests for integration.py config models."""

from __future__ import annotations

from integration import VercelSelector

# ── VercelSelector tests ───────────────────────────────────────────────────────


def test_vercel_selector_uppercases_states() -> None:
    """deploymentStates values should be uppercased regardless of input case."""
    selector = VercelSelector(
        query="true", deploymentStates=["ready", "Error", "BUILDING"]
    )
    assert selector.deployment_states == ["READY", "ERROR", "BUILDING"]


def test_vercel_selector_none_when_omitted() -> None:
    """deploymentStates should default to None when not provided."""
    selector = VercelSelector(query="true")
    assert selector.deployment_states is None


def test_vercel_selector_empty_list_preserved() -> None:
    """An explicit empty list should be kept as-is (not converted to None)."""
    selector = VercelSelector(query="true", deploymentStates=[])
    assert selector.deployment_states == []
