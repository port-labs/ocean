import asyncio
import uuid
from typing import Any

import httpx
from loguru import logger
from pydantic.v1 import BaseModel

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.tests.smoke.helpers.details import get_smoke_test_details

ECHO_MESSAGE_ACTION = "echo_message"
TRIGGER_FAKE_TASK_ACTION = "trigger_fake_task"
FAKE_TASK_COMPLETED_EVENT = "fake_task.completed"

_WORKFLOW_TERMINAL = frozenset({"COMPLETED"})


class WorkflowResources(BaseModel):
    suffix: str
    installation_id: str
    integration_provider: str
    echo_workflow_identifier: str
    trigger_fake_task_workflow_identifier: str


class CompletedRun(BaseModel):
    run_id: str
    status: str
    success: bool
    message: str | None = None


def get_workflow_resources(unique_suffix: str | None = None) -> WorkflowResources:
    details = get_smoke_test_details()
    prefix = "smoke-test-integration-"
    identifier = details.integration_identifier
    parts: list[str] = []
    if identifier.startswith(prefix):
        parts.append(identifier.removeprefix(prefix))
    if unique_suffix:
        parts.append(unique_suffix)
    resource_suffix = f"-{'-'.join(parts)}" if parts else ""

    return WorkflowResources(
        suffix=resource_suffix,
        installation_id=details.integration_identifier,
        # Workflow-service validates INTEGRATION_ACTION against enriched specs.
        # Smoke registers as this type so the org intersects the fake-integration spec.
        integration_provider="fake-integration",
        echo_workflow_identifier=f"echo-wf{resource_suffix}",
        trigger_fake_task_workflow_identifier=f"task-wf{resource_suffix}",
    )


def _integration_workflow_node(
    resources: WorkflowResources,
    node_identifier: str,
    title: str,
    action_type: str,
    execution_properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "identifier": node_identifier,
        "title": title,
        "icon": "Cookiecutter",
        "config": {
            "type": "INTEGRATION_ACTION",
            "installationId": resources.installation_id,
            "integrationProvider": resources.integration_provider,
            "integrationInvocationType": action_type,
            "integrationActionExecutionProperties": execution_properties,
            "onFailure": "terminate",
        },
        "variables": {},
        "verbose": False,
    }


def _self_serve_workflow(
    *,
    identifier: str,
    title: str,
    description: str,
    action_node: dict[str, Any],
) -> dict[str, Any]:
    trigger_id = "trigger"
    return {
        "identifier": identifier,
        "title": title,
        "icon": "Workflow",
        "description": description,
        "nodes": [
            {
                "identifier": trigger_id,
                "title": "Trigger",
                "config": {
                    "type": "SELF_SERVE_TRIGGER",
                    "published": True,
                    "userInputs": {
                        "properties": {
                            "message": {
                                "type": "string",
                                "title": "Message",
                            },
                            "taskName": {
                                "type": "string",
                                "title": "Task name",
                            },
                        }
                    },
                },
            },
            action_node,
        ],
        "connections": [
            {
                "sourceIdentifier": trigger_id,
                "targetIdentifier": action_node["identifier"],
            }
        ],
        "allowAnyoneToViewRuns": True,
    }


def build_echo_message_workflow(resources: WorkflowResources) -> dict[str, Any]:
    return _self_serve_workflow(
        identifier=resources.echo_workflow_identifier,
        title="Smoke test echo message workflow",
        description="Ocean core smoke test workflow for sync integration actions",
        action_node=_integration_workflow_node(
            resources,
            "echo-message",
            "Echo message",
            ECHO_MESSAGE_ACTION,
            {"message": "{{ .outputs.trigger.message }}"},
        ),
    )


def build_trigger_fake_task_workflow(resources: WorkflowResources) -> dict[str, Any]:
    return _self_serve_workflow(
        identifier=resources.trigger_fake_task_workflow_identifier,
        title="Smoke test trigger fake task workflow",
        description="Ocean core smoke test workflow for async integration actions",
        action_node=_integration_workflow_node(
            resources,
            "trigger-fake-task",
            "Trigger fake task",
            TRIGGER_FAKE_TASK_ACTION,
            {
                "taskName": "{{ .outputs.trigger.taskName }}",
                "reportTaskStatus": True,
            },
        ),
    )


async def _upsert_workflow(port_client: PortClient, workflow: dict[str, Any]) -> None:
    headers = await port_client.auth.headers()
    create = await port_client.client.post(
        f"{port_client.auth.api_url}/workflows",
        json=workflow,
        headers=headers,
    )
    if create.is_error and create.status_code != 409:
        logger.error(
            "Failed to create smoke workflow {identifier}: {body}",
            identifier=workflow["identifier"],
            body=create.text,
        )
    if create.status_code == 409:
        update = await port_client.client.put(
            f"{port_client.auth.api_url}/workflows/{workflow['identifier']}",
            json=workflow,
            headers=headers,
        )
        handle_port_status_code(update, should_log=False)
        return
    handle_port_status_code(create, should_log=False)


async def _delete_workflow(port_client: PortClient, identifier: str) -> None:
    response = await port_client.client.delete(
        f"{port_client.auth.api_url}/workflows/{identifier}",
        headers=await port_client.auth.headers(),
    )
    if response.status_code != 404:
        handle_port_status_code(response, should_log=False)


async def setup_workflow_resources(
    port_client: PortClient, unique_suffix: str | None = None
) -> WorkflowResources:
    resources = get_workflow_resources(unique_suffix)
    await asyncio.gather(
        _upsert_workflow(port_client, build_echo_message_workflow(resources)),
        _upsert_workflow(port_client, build_trigger_fake_task_workflow(resources)),
    )
    logger.info("Configured workflows for smoke test", resources=resources)
    return resources


async def cleanup_workflow_resources(
    port_client: PortClient, resources: WorkflowResources
) -> None:
    await asyncio.gather(
        _delete_workflow(port_client, resources.echo_workflow_identifier),
        _delete_workflow(port_client, resources.trigger_fake_task_workflow_identifier),
    )


async def trigger_workflow(
    port_client: PortClient,
    workflow_identifier: str,
    inputs: dict[str, Any],
) -> str:
    response = await port_client.client.post(
        f"{port_client.auth.api_url}/workflows/{workflow_identifier}/runs",
        json={"inputs": inputs},
        headers=await port_client.auth.headers(),
    )
    handle_port_status_code(response)
    return response.json()["workflowRun"]["identifier"]


async def _get_workflow_run(port_client: PortClient, run_id: str) -> dict[str, Any]:
    response = await port_client.client.get(
        f"{port_client.auth.api_url}/workflows/runs/{run_id}",
        headers=await port_client.auth.headers(),
    )
    handle_port_status_code(response)
    return response.json()["workflowRun"]


async def wait_for_workflow_node_external_id(
    port_client: PortClient,
    run_id: str,
    timeout_seconds: float = 60,
    poll_interval_seconds: float = 1,
) -> str:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        run = await _get_workflow_run(port_client, run_id)
        for node_run in run.get("nodeRuns") or []:
            external_id = node_run.get("externalRunId")
            if external_id:
                return external_id
        await asyncio.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Workflow run {run_id} did not get a node external id within {timeout_seconds}s"
    )


def task_id_from_external_id(external_id: str) -> str:
    prefix = "fake_task_"
    if not external_id.startswith(prefix):
        raise ValueError(f"Unexpected external id format: {external_id}")
    return external_id.removeprefix(prefix)


async def simulate_fake_task_webhook(
    integration_webhook_url: str,
    task_id: str,
    status: str = "success",
) -> None:
    payload = {
        "event": FAKE_TASK_COMPLETED_EVENT,
        "task": {"id": task_id, "status": status},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(integration_webhook_url, json=payload)
        response.raise_for_status()


async def wait_for_workflow_run(
    port_client: PortClient,
    run_id: str,
    timeout_seconds: float = 120,
    poll_interval_seconds: float = 2,
) -> CompletedRun:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        run = await _get_workflow_run(port_client, run_id)
        status = run.get("status")
        if status in _WORKFLOW_TERMINAL:
            status_label = run.get("statusLabel")
            message = (
                status_label.get("message") if isinstance(status_label, dict) else None
            )
            return CompletedRun(
                run_id=run_id,
                status=status,
                success=run.get("result") == "SUCCESS",
                message=message,
            )
        await asyncio.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Workflow run {run_id} did not complete within {timeout_seconds}s"
    )


def new_workflow_resource_suffix() -> str:
    return uuid.uuid4().hex[:8]
