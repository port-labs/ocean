from os import environ
from typing import Tuple

import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.tests.smoke.helpers.details import SmokeTestDetails
from port_ocean.tests.smoke.helpers.workflows import (
    WorkflowResources,
    simulate_fake_task_webhook,
    task_id_from_external_id,
    trigger_workflow,
    wait_for_workflow_node_external_id,
    wait_for_workflow_run,
)

pytestmark = [pytest.mark.smoke, pytest.mark.smoke_configset("workflows")]

requires_running_integration = pytest.mark.skipif(
    environ.get(
        "SMOKE_TEST_WEBHOOK_URL", environ.get("SMOKE_TEST_INTEGRATION_WEBHOOK_URL")
    )
    is None,
    reason="Run make smoke/up CONFIGSET=workflows before workflow smoke tests",
)


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
@requires_running_integration
async def test_echo_message_workflow_run(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
    workflow_resources: WorkflowResources,
) -> None:
    _, port_client = port_client_for_fake_integration
    run_id = await trigger_workflow(
        port_client,
        workflow_resources.echo_workflow_identifier,
        {"message": "hello from smoke workflow"},
    )
    completed = await wait_for_workflow_run(port_client, run_id)
    assert completed.success, completed.message


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
@requires_running_integration
async def test_trigger_fake_task_workflow_run(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
    workflow_resources: WorkflowResources,
) -> None:
    webhook_url = (
        environ.get("SMOKE_TEST_WEBHOOK_URL")
        or environ["SMOKE_TEST_INTEGRATION_WEBHOOK_URL"]
    )

    _, port_client = port_client_for_fake_integration
    run_id = await trigger_workflow(
        port_client,
        workflow_resources.trigger_fake_task_workflow_identifier,
        {"taskName": "smoke-async-workflow-task"},
    )
    external_id = await wait_for_workflow_node_external_id(port_client, run_id)
    await simulate_fake_task_webhook(
        webhook_url, task_id_from_external_id(external_id), status="success"
    )
    completed = await wait_for_workflow_run(port_client, run_id)
    assert completed.success, completed.message
