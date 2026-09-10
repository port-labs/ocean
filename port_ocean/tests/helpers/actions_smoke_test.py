import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger
from pydantic.v1 import BaseModel

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.tests.helpers.smoke_test import SmokeTestDetails, get_smoke_test_details

ECHO_MESSAGE_ACTION = "echo_message"
TRIGGER_FAKE_TASK_ACTION = "trigger_fake_task"
FAKE_TASK_COMPLETED_EVENT = "fake_task.completed"


class ActionsSmokeTestResources(BaseModel):
    suffix: str
    installation_id: str
    integration_provider: str
    echo_action_identifier: str
    trigger_fake_task_action_identifier: str
    echo_workflow_identifier: str
    trigger_fake_task_workflow_identifier: str


@dataclass(frozen=True)
class CompletedRun:
    run_id: str
    status: str
    success: bool
    message: str | None


def get_actions_smoke_resources() -> ActionsSmokeTestResources:
    details = get_smoke_test_details()
    suffix = details.integration_identifier.removeprefix("smoke-test-integration")
    suffix = suffix.removeprefix("-")
    resource_suffix = f"-{suffix}" if suffix else ""

    return ActionsSmokeTestResources(
        suffix=resource_suffix,
        installation_id=details.integration_identifier,
        integration_provider=details.integration_type,
        echo_action_identifier=f"smoke_echo_message{resource_suffix}",
        trigger_fake_task_action_identifier=f"smoke_trigger_fake_task{resource_suffix}",
        echo_workflow_identifier=f"smoke_echo_message_wf{resource_suffix}",
        trigger_fake_task_workflow_identifier=f"smoke_trigger_fake_task_wf{resource_suffix}",
    )


def _integration_action_invocation(
    resources: ActionsSmokeTestResources,
    action_type: str,
    execution_properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "INTEGRATION_ACTION",
        "installationId": resources.installation_id,
        "integrationActionType": action_type,
        "integrationActionExecutionProperties": execution_properties,
    }


def build_echo_message_action(resources: ActionsSmokeTestResources) -> dict[str, Any]:
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
        "trigger": {
            "type": "self-service",
            "operation": "CREATE",
            "userInputs": {
                "properties": {
                    "message": {
                        "type": "string",
                        "title": "Message",
                    }
                },
                "required": ["message"],
            },
        },
        "publish": True,
    }


def build_trigger_fake_task_action(
    resources: ActionsSmokeTestResources,
) -> dict[str, Any]:
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
        "trigger": {
            "type": "self-service",
            "operation": "CREATE",
            "userInputs": {
                "properties": {
                    "taskName": {
                        "type": "string",
                        "title": "Task name",
                    }
                },
                "required": ["taskName"],
            },
        },
        "publish": True,
    }


def _integration_workflow_node(
    resources: ActionsSmokeTestResources,
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


def build_echo_message_workflow(resources: ActionsSmokeTestResources) -> dict[str, Any]:
    trigger_id = "trigger"
    action_id = "echo_message"
    return {
        "identifier": resources.echo_workflow_identifier,
        "title": "Smoke test echo message workflow",
        "icon": "Workflow",
        "description": "Ocean core smoke test workflow for sync integration actions",
        "nodes": [
            {
                "identifier": trigger_id,
                "title": "Trigger",
                "config": {"type": "SELF_SERVE_TRIGGER", "published": True},
            },
            _integration_workflow_node(
                resources,
                action_id,
                "Echo message",
                ECHO_MESSAGE_ACTION,
                {"message": "{{ .inputs.message }}"},
            ),
        ],
        "connections": [
            {
                "sourceIdentifier": trigger_id,
                "targetIdentifier": action_id,
            }
        ],
        "allowAnyoneToViewRuns": True,
    }


def build_trigger_fake_task_workflow(
    resources: ActionsSmokeTestResources,
) -> dict[str, Any]:
    trigger_id = "trigger"
    action_id = "trigger_fake_task"
    return {
        "identifier": resources.trigger_fake_task_workflow_identifier,
        "title": "Smoke test trigger fake task workflow",
        "icon": "Workflow",
        "description": "Ocean core smoke test workflow for async integration actions",
        "nodes": [
            {
                "identifier": trigger_id,
                "title": "Trigger",
                "config": {"type": "SELF_SERVE_TRIGGER", "published": True},
            },
            _integration_workflow_node(
                resources,
                action_id,
                "Trigger fake task",
                TRIGGER_FAKE_TASK_ACTION,
                {
                    "taskName": "{{ .inputs.taskName }}",
                    "reportTaskStatus": True,
                },
            ),
        ],
        "connections": [
            {
                "sourceIdentifier": trigger_id,
                "targetIdentifier": action_id,
            }
        ],
        "allowAnyoneToViewRuns": True,
    }


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


async def setup_actions_smoke_test(
    port_client: PortClient,
) -> ActionsSmokeTestResources:
    resources = get_actions_smoke_resources()
    await _upsert_action(port_client, build_echo_message_action(resources))
    await _upsert_action(port_client, build_trigger_fake_task_action(resources))
    await _upsert_workflow(port_client, build_echo_message_workflow(resources))
    await _upsert_workflow(port_client, build_trigger_fake_task_workflow(resources))
    logger.info(
        "Configured actions and workflows for actions smoke test", resources=resources
    )
    return resources


async def cleanup_actions_smoke_test(
    port_client: PortClient, resources: ActionsSmokeTestResources
) -> None:
    for identifier in (
        resources.echo_action_identifier,
        resources.trigger_fake_task_action_identifier,
    ):
        response = await port_client.client.delete(
            f"{port_client.auth.api_url}/actions/{identifier}",
            headers=await port_client.auth.headers(),
        )
        if response.status_code != 404:
            handle_port_status_code(response, should_log=False)

    for identifier in (
        resources.echo_workflow_identifier,
        resources.trigger_fake_task_workflow_identifier,
    ):
        response = await port_client.client.delete(
            f"{port_client.auth.api_url}/workflows/{identifier}",
            headers=await port_client.auth.headers(),
        )
        if response.status_code != 404:
            handle_port_status_code(response, should_log=False)


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


async def wait_for_action_run(
    port_client: PortClient,
    run_id: str,
    timeout_seconds: float = 120,
    poll_interval_seconds: float = 2,
) -> CompletedRun:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        run = await get_action_run(port_client, run_id)
        status = run.get("status")
        if status in {"COMPLETED", "FAILED"}:
            return CompletedRun(
                run_id=run_id,
                status=status,
                success=status == "COMPLETED",
                message=run.get("message"),
            )
        await asyncio.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Action run {run_id} did not complete within {timeout_seconds}s"
    )


async def wait_for_workflow_run(
    port_client: PortClient,
    run_id: str,
    timeout_seconds: float = 120,
    poll_interval_seconds: float = 2,
) -> CompletedRun:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        response = await port_client.client.get(
            f"{port_client.auth.api_url}/workflows/runs/{run_id}",
            headers=await port_client.auth.headers(),
        )
        handle_port_status_code(response)
        run = response.json()["run"]
        status = run.get("status")
        if status in {"COMPLETED", "FAILED", "TERMINATED"}:
            return CompletedRun(
                run_id=run_id,
                status=status,
                success=status == "COMPLETED",
                message=run.get("message"),
            )
        await asyncio.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Workflow run {run_id} did not complete within {timeout_seconds}s"
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


def get_smoke_test_details_for_actions() -> SmokeTestDetails:
    return get_smoke_test_details()
