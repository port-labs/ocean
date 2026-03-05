"""Unit tests for integration.py config models and helpers/utils.py."""

from __future__ import annotations

from integration import VercelSelector
from vercel.helpers.utils import extract_entity

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


# ── extract_entity tests ───────────────────────────────────────────────────────


def test_extract_entity_deployment() -> None:
    """Should pull the nested deployment dict from the event payload."""
    deployment = {"uid": "dpl_abc", "state": "READY"}
    payload = {"deployment": deployment, "project": {"id": "prj_xyz"}}
    assert extract_entity("deployment", payload) == deployment


def test_extract_entity_project() -> None:
    """Should pull the nested project dict from the event payload."""
    project = {"id": "prj_xyz", "name": "my-app"}
    payload = {"project": project}
    assert extract_entity("project", payload) == project


def test_extract_entity_domain() -> None:
    """Should pull the nested domain dict from the event payload."""
    domain = {"name": "app.example.com"}
    payload = {"domain": domain}
    assert extract_entity("domain", payload) == domain


def test_extract_entity_falls_back_to_payload() -> None:
    """Unknown kind should return the whole payload as-is."""
    payload = {"id": "something", "foo": "bar"}
    assert extract_entity("unknown", payload) == payload


def test_extract_entity_missing_nested_key_falls_back() -> None:
    """If the expected nested key is absent, fall back to the whole payload."""
    payload = {"project": {"id": "prj_xyz"}}
    # 'deployment' key is not in payload — should return the whole payload
    result = extract_entity("deployment", payload)
    assert result == payload
