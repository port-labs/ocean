from os import environ
from typing import Tuple

import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.tests.smoke.helpers.actions import (
    ActionResources,
    simulate_fake_task_webhook,
    task_id_from_external_id,
    trigger_self_service_action,
    trigger_workflow,
    wait_for_action_run,
    wait_for_action_run_external_id,
    wait_for_workflow_run,
)
from port_ocean.tests.smoke.helpers.details import SmokeTestDetails

pytestmark = [
    pytest.mark.smoke,
    # Omit smoke_config while skipped so run-all does not boot the actions container.
    # Restore: pytest.mark.smoke_config("actions"),
    # Port PUT /v1/actions rejects custom Ocean action types: integrationActionType is
    # enum-limited to GitHub types (dispatch_workflow, …). Workflows already accept
    # free-form integrationInvocationType. Unskip + restore smoke_config when port-api
    # allows free-form types (local Port patch ready in apps/port-api schema).
    pytest.mark.skip(
        reason=(
            "Port API 422: integrationActionType enum does not allow echo_message/"
            "trigger_fake_task (see INTEGRATION_ACTION_TYPES in port-api)"
        )
    ),
]

requires_running_integration = pytest.mark.skipif(
    environ.get(
        "SMOKE_TEST_WEBHOOK_URL", environ.get("SMOKE_TEST_INTEGRATION_WEBHOOK_URL")
    )
    is None,
    reason="Run make smoke/up CONFIG=actions before action smoke tests",
)


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
@requires_running_integration
async def test_echo_message_action_run(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
    action_resources: ActionResources,
) -> None:
    _, port_client = port_client_for_fake_integration
    run_id = await trigger_self_service_action(
        port_client,
        action_resources.echo_action_identifier,
        {"message": "hello from smoke test"},
    )
    completed = await wait_for_action_run(port_client, run_id)
    assert completed.success


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
@requires_running_integration
async def test_echo_message_workflow_run(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
    action_resources: ActionResources,
) -> None:
    _, port_client = port_client_for_fake_integration
    run_id = await trigger_workflow(
        port_client,
        action_resources.echo_workflow_identifier,
        {"message": "hello from smoke workflow"},
    )
    completed = await wait_for_workflow_run(port_client, run_id)
    assert completed.success


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
@requires_running_integration
async def test_trigger_fake_task_action_run(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
    action_resources: ActionResources,
) -> None:
    webhook_url = (
        environ.get("SMOKE_TEST_WEBHOOK_URL")
        or environ["SMOKE_TEST_INTEGRATION_WEBHOOK_URL"]
    )

    _, port_client = port_client_for_fake_integration
    run_id = await trigger_self_service_action(
        port_client,
        action_resources.trigger_fake_task_action_identifier,
        {"taskName": "smoke-async-task"},
    )
    external_id = await wait_for_action_run_external_id(port_client, run_id)
    await simulate_fake_task_webhook(
        webhook_url, task_id_from_external_id(external_id), status="success"
    )
    completed = await wait_for_action_run(port_client, run_id)
    assert completed.success


@pytest.mark.skip(
    reason="Workflow node run external id polling for async actions is not wired yet"
)
@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
@requires_running_integration
async def test_trigger_fake_task_workflow_run(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
    action_resources: ActionResources,
) -> None:
    _, port_client = port_client_for_fake_integration
    run_id = await trigger_workflow(
        port_client,
        action_resources.trigger_fake_task_workflow_identifier,
        {"taskName": "smoke-async-workflow-task"},
    )
    completed = await wait_for_workflow_run(port_client, run_id)
    assert completed.success
