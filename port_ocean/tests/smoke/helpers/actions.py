import asyncio
import uuid
from typing import Any, Awaitable, Callable

import httpx
from loguru import logger
from pydantic.v1 import BaseModel

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.tests.smoke.helpers.details import get_smoke_test_details

ECHO_MESSAGE_ACTION = "echo_message"
TRIGGER_FAKE_TASK_ACTION = "trigger_fake_task"
FAKE_TASK_COMPLETED_EVENT = "fake_task.completed"

_ACTION_TERMINAL = frozenset({"SUCCESS", "FAILURE"})
_WORKFLOW_TERMINAL = frozenset({"COMPLETED", "FAILED", "TERMINATED"})


class ActionResources(BaseModel):
    suffix: str
    installation_id: str
    integration_provider: str
    echo_action_identifier: str
    trigger_fake_task_action_identifier: str
    echo_workflow_identifier: str
    trigger_fake_task_workflow_identifier: str


class CompletedRun(BaseModel):
    run_id: str
    status: str
    success: bool
    message: str | None = None


def get_action_resources(unique_suffix: str | None = None) -> ActionResources:
    details = get_smoke_test_details()
    prefix = "smoke-test-integration-"
    identifier = details.integration_identifier
    parts: list[str] = []
    if identifier.startswith(prefix):
        parts.append(identifier.removeprefix(prefix))
    if unique_suffix:
        parts.append(unique_suffix)
    resource_suffix = f"-{'-'.join(parts)}" if parts else ""

    return ActionResources(
        suffix=resource_suffix,
        installation_id=details.integration_identifier,
        integration_provider=details.integration_type,
        echo_action_identifier=f"smoke_echo_message{resource_suffix}",
        trigger_fake_task_action_identifier=f"smoke_trigger_fake_task{resource_suffix}",
        echo_workflow_identifier=f"smoke_echo_message_wf{resource_suffix}",
        trigger_fake_task_workflow_identifier=f"smoke_trigger_fake_task_wf{resource_suffix}",
    )


def _integration_action_invocation(
    resources: ActionResources,
    action_type: str,
    execution_properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "INTEGRATION_ACTION",
        "installationId": resources.installation_id,
        "integrationActionType": action_type,
        "integrationActionExecutionProperties": execution_properties,
    }


def _self_service_trigger(properties: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "self-service",
        "operation": "CREATE",
        "userInputs": {
            "properties": properties,
            "required": list(properties),
        },
    }


def build_echo_message_action(resources: ActionResources) -> dict[str, Any]:
    return {
        "identifier": resources.echo_action_identifier,
        "title": "Smoke test echo message",
        "icon": "Cookiecutter",
        "description": "Ocean core smoke test for sync integration actions",
        "invocationMethod": _integration_action_invocation(
            resources,
            ECHO_MESSAGE_ACTION,
            {"message": "{{ .inputs.message }}"},
        ),
        "trigger": _self_service_trigger(
            {"message": {"type": "string", "title": "Message"}}
        ),
        "publish": True,
    }


def build_trigger_fake_task_action(resources: ActionResources) -> dict[str, Any]:
    return {
        "identifier": resources.trigger_fake_task_action_identifier,
        "title": "Smoke test trigger fake task",
        "icon": "Cookiecutter",
        "description": "Ocean core smoke test for async integration actions",
        "invocationMethod": _integration_action_invocation(
            resources,
            TRIGGER_FAKE_TASK_ACTION,
            {
                "taskName": "{{ .inputs.taskName }}",
                "reportTaskStatus": True,
            },
        ),
        "trigger": _self_service_trigger(
            {"taskName": {"type": "string", "title": "Task name"}}
        ),
        "publish": True,
    }


def _integration_workflow_node(
    resources: ActionResources,
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
                "config": {"type": "SELF_SERVE_TRIGGER", "published": True},
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


def build_echo_message_workflow(resources: ActionResources) -> dict[str, Any]:
    return _self_serve_workflow(
        identifier=resources.echo_workflow_identifier,
        title="Smoke test echo message workflow",
        description="Ocean core smoke test workflow for sync integration actions",
        action_node=_integration_workflow_node(
            resources,
            "echo_message",
            "Echo message",
            ECHO_MESSAGE_ACTION,
            {"message": "{{ .inputs.message }}"},
        ),
    )


def build_trigger_fake_task_workflow(resources: ActionResources) -> dict[str, Any]:
    return _self_serve_workflow(
        identifier=resources.trigger_fake_task_workflow_identifier,
        title="Smoke test trigger fake task workflow",
        description="Ocean core smoke test workflow for async integration actions",
        action_node=_integration_workflow_node(
            resources,
            "trigger_fake_task",
            "Trigger fake task",
            TRIGGER_FAKE_TASK_ACTION,
            {
                "taskName": "{{ .inputs.taskName }}",
                "reportTaskStatus": True,
            },
        ),
    )


async def _upsert_action(port_client: PortClient, action: dict[str, Any]) -> None:
    response = await port_client.client.put(
        f"{port_client.auth.api_url}/actions/{action['identifier']}",
        json=action,
        headers=await port_client.auth.headers(),
    )
    handle_port_status_code(response, should_log=False)


async def _upsert_workflow(port_client: PortClient, workflow: dict[str, Any]) -> None:
    response = await port_client.client.put(
        f"{port_client.auth.api_url}/workflows/{workflow['identifier']}",
        json=workflow,
        headers=await port_client.auth.headers(),
    )
    handle_port_status_code(response, should_log=False)


async def _delete_resource(port_client: PortClient, kind: str, identifier: str) -> None:
    response = await port_client.client.delete(
        f"{port_client.auth.api_url}/{kind}/{identifier}",
        headers=await port_client.auth.headers(),
    )
    if response.status_code != 404:
        handle_port_status_code(response, should_log=False)


async def setup_action_resources(
    port_client: PortClient, unique_suffix: str | None = None
) -> ActionResources:
    resources = get_action_resources(unique_suffix)
    await asyncio.gather(
        _upsert_action(port_client, build_echo_message_action(resources)),
        _upsert_action(port_client, build_trigger_fake_task_action(resources)),
        _upsert_workflow(port_client, build_echo_message_workflow(resources)),
        _upsert_workflow(port_client, build_trigger_fake_task_workflow(resources)),
    )
    logger.info("Configured actions and workflows for smoke test", resources=resources)
    return resources


async def cleanup_action_resources(
    port_client: PortClient, resources: ActionResources
) -> None:
    await asyncio.gather(
        _delete_resource(port_client, "actions", resources.echo_action_identifier),
        _delete_resource(
            port_client, "actions", resources.trigger_fake_task_action_identifier
        ),
        _delete_resource(port_client, "workflows", resources.echo_workflow_identifier),
        _delete_resource(
            port_client, "workflows", resources.trigger_fake_task_workflow_identifier
        ),
    )


async def trigger_self_service_action(
    port_client: PortClient,
    action_identifier: str,
    properties: dict[str, Any],
) -> str:
    response = await port_client.client.post(
        f"{port_client.auth.api_url}/actions/{action_identifier}/runs",
        json={"properties": properties},
        headers=await port_client.auth.headers(),
    )
    handle_port_status_code(response)
    return response.json()["run"]["id"]


async def trigger_workflow(
    port_client: PortClient,
    workflow_identifier: str,
    properties: dict[str, Any],
) -> str:
    response = await port_client.client.post(
        f"{port_client.auth.api_url}/workflows/{workflow_identifier}/runs",
        json={"properties": properties},
        headers=await port_client.auth.headers(),
    )
    handle_port_status_code(response)
    return response.json()["run"]["id"]


async def get_action_run(port_client: PortClient, run_id: str) -> dict[str, Any]:
    response = await port_client.client.get(
        f"{port_client.auth.api_url}/actions/runs/{run_id}",
        headers=await port_client.auth.headers(),
    )
    handle_port_status_code(response)
    return response.json()["run"]


async def wait_for_action_run_external_id(
    port_client: PortClient,
    run_id: str,
    timeout_seconds: float = 60,
    poll_interval_seconds: float = 1,
) -> str:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        run = await get_action_run(port_client, run_id)
        external_id = run.get("externalRunId")
        if external_id:
            return external_id
        await asyncio.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Action run {run_id} did not get an external id within {timeout_seconds}s"
    )


def task_id_from_external_id(external_id: str) -> str:
    prefix = "fake_task_"
    if not external_id.startswith(prefix):
        raise ValueError(f"Unexpected external id format: {external_id}")
    return external_id.removeprefix(prefix)


async def _wait_for_terminal_run(
    *,
    run_id: str,
    fetch_run: Callable[[], Awaitable[dict[str, Any]]],
    terminal: frozenset[str],
    success_statuses: frozenset[str],
    label: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> CompletedRun:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        run = await fetch_run()
        status = run.get("status")
        if status in terminal:
            return CompletedRun(
                run_id=run_id,
                status=status,
                success=status in success_statuses,
                message=run.get("message"),
            )
        await asyncio.sleep(poll_interval_seconds)
    raise TimeoutError(f"{label} {run_id} did not complete within {timeout_seconds}s")


async def wait_for_action_run(
    port_client: PortClient,
    run_id: str,
    timeout_seconds: float = 120,
    poll_interval_seconds: float = 2,
) -> CompletedRun:
    return await _wait_for_terminal_run(
        run_id=run_id,
        fetch_run=lambda: get_action_run(port_client, run_id),
        terminal=_ACTION_TERMINAL,
        success_statuses=frozenset({"SUCCESS"}),
        label="Action run",
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


async def wait_for_workflow_run(
    port_client: PortClient,
    run_id: str,
    timeout_seconds: float = 120,
    poll_interval_seconds: float = 2,
) -> CompletedRun:
    async def fetch_run() -> dict[str, Any]:
        response = await port_client.client.get(
            f"{port_client.auth.api_url}/workflows/runs/{run_id}",
            headers=await port_client.auth.headers(),
        )
        handle_port_status_code(response)
        return response.json()["run"]

    return await _wait_for_terminal_run(
        run_id=run_id,
        fetch_run=fetch_run,
        terminal=_WORKFLOW_TERMINAL,
        success_statuses=frozenset({"COMPLETED"}),
        label="Workflow run",
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


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


def new_action_resource_suffix() -> str:
    return uuid.uuid4().hex[:8]
