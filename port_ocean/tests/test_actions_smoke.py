from collections.abc import AsyncGenerator
from os import environ
from typing import Tuple

import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.tests.helpers.actions_smoke_test import (
    ActionsSmokeTestResources,
    cleanup_actions_smoke_test,
    setup_actions_smoke_test,
    simulate_fake_task_webhook,
    task_id_from_external_id,
    trigger_self_service_action,
    trigger_workflow,
    wait_for_action_run,
    wait_for_action_run_external_id,
    wait_for_workflow_run,
)

pytestmark = pytest.mark.smoke


@pytest.fixture
async def actions_smoke_resources(
    port_client_for_fake_integration: Tuple[object, PortClient],
) -> AsyncGenerator[ActionsSmokeTestResources, None]:
    _, port_client = port_client_for_fake_integration
    resources = await setup_actions_smoke_test(port_client)
    try:
        yield resources
    finally:
        await cleanup_actions_smoke_test(port_client, resources)


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
async def test_echo_message_action_run(
    port_client_for_fake_integration: Tuple[object, PortClient],
    actions_smoke_resources: ActionsSmokeTestResources,
) -> None:
    _, port_client = port_client_for_fake_integration
    run_id = await trigger_self_service_action(
        port_client,
        actions_smoke_resources.echo_action_identifier,
        {"message": "hello from smoke test"},
    )
    completed = await wait_for_action_run(port_client, run_id)
    assert completed.success


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
async def test_echo_message_workflow_run(
    port_client_for_fake_integration: Tuple[object, PortClient],
    actions_smoke_resources: ActionsSmokeTestResources,
) -> None:
    _, port_client = port_client_for_fake_integration
    run_id = await trigger_workflow(
        port_client,
        actions_smoke_resources.echo_workflow_identifier,
        {"message": "hello from smoke workflow"},
    )
    completed = await wait_for_workflow_run(port_client, run_id)
    assert completed.success


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
async def test_trigger_fake_task_action_run(
    port_client_for_fake_integration: Tuple[object, PortClient],
    actions_smoke_resources: ActionsSmokeTestResources,
) -> None:
    webhook_url = environ.get("SMOKE_TEST_INTEGRATION_WEBHOOK_URL")
    assert (
        webhook_url
    ), "SMOKE_TEST_INTEGRATION_WEBHOOK_URL is required for async actions"

    _, port_client = port_client_for_fake_integration
    run_id = await trigger_self_service_action(
        port_client,
        actions_smoke_resources.trigger_fake_task_action_identifier,
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
async def test_trigger_fake_task_workflow_run(
    port_client_for_fake_integration: Tuple[object, PortClient],
    actions_smoke_resources: ActionsSmokeTestResources,
) -> None:
    webhook_url = environ.get("SMOKE_TEST_INTEGRATION_WEBHOOK_URL")
    assert (
        webhook_url
    ), "SMOKE_TEST_INTEGRATION_WEBHOOK_URL is required for async actions"

    _, port_client = port_client_for_fake_integration
    run_id = await trigger_workflow(
        port_client,
        actions_smoke_resources.trigger_fake_task_workflow_identifier,
        {"taskName": "smoke-async-workflow-task"},
    )
    completed = await wait_for_workflow_run(port_client, run_id)
    assert completed.success
