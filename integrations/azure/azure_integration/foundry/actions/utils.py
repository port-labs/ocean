from __future__ import annotations

from typing import Any

from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from azure_integration.foundry.core.exporters.project_exporter import (
    foundry_project_from_arm_id,
)
from azure_integration.foundry.helpers.utils import project_name_from_endpoint


def invoke_scope_from_run(run: Any) -> tuple[str, str, str | None] | None:
    """Project endpoint, project id, optional agent id from an invoke run."""
    if not isinstance(run, IntegrationRun):
        return None
    props = run.output if isinstance(run, WorkflowNodeRun) else run.execution_properties
    project = foundry_project_from_arm_id(str(props.get("projectArmId") or ""))
    endpoint = (
        (project.endpoint if project else None)
        or props.get("projectEndpoint")
        or run.execution_properties.get("projectEndpoint")
    )
    if not isinstance(endpoint, str) or not endpoint.strip():
        return None
    agent_id = str(run.execution_properties.get("agentId") or "").strip() or None
    return endpoint.strip(), project_name_from_endpoint(endpoint), agent_id
