# Testing actions

Two things about this setup are easy to get wrong: tests patch the `ocean` object **on the
module under test** rather than globally, and executor tests build **real** run models instead
of mocks so that `execution_properties` behaves like production.

## Executor tests

Mirror the executor's path, e.g. `tests/actions/test_trigger_pipeline_executor.py`.

```python
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from gitlab.actions.trigger_pipeline_executor import TriggerPipelineExecutor
from gitlab.helpers.exceptions import (
    GitlabTriggerPipelineError,
    MissingExecutionPropertyError,
)

PIPELINE_RESPONSE = {
    "id": 99,
    "project_id": 42,
    "web_url": "https://gitlab.com/my-group/my-project/-/pipelines/99",
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="gitlab",
            integrationInvocationType="trigger_pipeline",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> TriggerPipelineExecutor:
    # Patch the client factory where the abstract executor imports it, so __init__
    # does not build a real client.
    with patch("gitlab.actions.abstract_gitlab_executor.create_gitlab_client"):
        ex = TriggerPipelineExecutor()
        ex.client = MagicMock()
        ex.client.trigger_pipeline = AsyncMock(return_value=PIPELINE_RESPONSE)
        return ex


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.update_run_started = AsyncMock()
    client.report_run_completed = AsyncMock()
    client.post_run_log = AsyncMock()
    return client


@pytest.mark.asyncio
class TestTriggerPipelineExecutor:
    async def test_happy_path(
        self, executor: TriggerPipelineExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({"project": "my-group/my-project", "ref": "main"})
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_port_client.update_run_started.assert_called_once_with(
            run, PIPELINE_RESPONSE["web_url"], "gl_42_99"
        )
        # An async action must leave the run in progress for its webhook.
        mock_port_client.report_run_completed.assert_not_called()

    async def test_missing_required_input(
        self, executor: TriggerPipelineExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({"ref": "main"})
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_upstream_http_error(
        self, executor: TriggerPipelineExecutor, mock_port_client: MagicMock
    ) -> None:
        response = httpx.Response(
            403, json={"message": "forbidden"}, request=httpx.Request("POST", "http://x")
        )
        executor.client.trigger_pipeline = AsyncMock(
            side_effect=httpx.HTTPStatusError("403", request=response.request, response=response)
        )
        run = make_run({"project": "p", "ref": "main"})
        with patch("gitlab.actions.trigger_pipeline_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(GitlabTriggerPipelineError):
                await executor.execute(run)
```

Key points:

- Patch `<module.under.test>.ocean`, not `port_ocean.context.ocean`. Each module holds its own
  reference from `from port_ocean.context.ocean import ocean`. Patching the wrong path leaves
  the real context in place and the test fails on an uninitialized context.
- Every `port_client` method the executor awaits must be an `AsyncMock`. A plain `MagicMock`
  returns a non-awaitable and fails with a confusing error.
- Assert the *exact* `update_run_started` call, including the external id string. That literal
  is the contract between executor and webhook processor, so pinning it catches a change on
  either side.
- Assert `report_run_completed.assert_not_called()` for async actions. It is the only thing
  that stops someone "fixing" an action by completing it early.
- Never pass or assert a `status_label` / label argument — no client method accepts one.
- If the integration's `__init__` patches more than one module (some patch
  `actions.utils.ocean` too), patch all of them.

Use `ActionRun` instead of `WorkflowNodeRun` if the integration's tests do, or cover both. The
executor should behave identically; the unified client methods absorb the difference.

## Action webhook processor tests

```python
@pytest.mark.asyncio
class TestTriggerPipelineWebhookProcessor:
    async def test_terminal_success_completes_run(
        self, processor: TriggerPipelineWebhookProcessor, resource_config: MagicMock
    ) -> None:
        run = make_run({"reportPipelineStatus": True})
        module = "gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor"
        with patch(f"{module}.ocean") as mock_ocean:
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=run)
            mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
            mock_ocean.port_client.post_run_log = AsyncMock()
            mock_ocean.port_client.report_run_completed = AsyncMock()

            await processor.handle_event(payload, resource_config)

            mock_ocean.port_client.report_run_completed.assert_called_once_with(
                run, True, "Pipeline completed: success"
            )
```

Note that `is_run_in_progress` is a **sync** method — mock it with `MagicMock`, not
`AsyncMock`. The other three are async. Getting this backwards makes the guard truthy on a
coroutine object, so the test passes for the wrong reason.

Cover each guard, since each is a distinct production failure mode:

- `find_run_by_external_id` returns `None` → no completion reported, empty results
- the opt-in input is `False` → no completion reported
- `is_run_in_progress` is `False` → no completion reported (duplicate webhook)
- non-terminal status → `should_process_event` returns `False`
- each terminal status → correct `success` boolean and label

Also assert `handle_event` returns empty `updated_raw_results` and `deleted_raw_results`, unless
the processor deliberately upserts catalog entities as well.

## Partition key tests

If you overrode `_get_partition_key`, assert both branches directly. It runs in
`_poll_action_runs`, outside the try/except that reports failures, so a raise there drops the
run without ever telling Port.

```python
    async def test_partition_key(self, executor: DispatchWorkflowExecutor) -> None:
        run = make_run({"org": "port-labs", "repo": "ocean", "workflow": "ci.yml"})
        assert await executor._get_partition_key(run) == "port-labs/ocean/ci.yml"

    async def test_partition_key_missing_inputs_returns_none(
        self, executor: DispatchWorkflowExecutor
    ) -> None:
        assert await executor._get_partition_key(make_run({})) is None
```

## Running

```bash
cd integrations/<name>
make test
make lint
```

If `make lint` reports a formatting failure, run the integration venv's formatter
(`.venv/bin/black .`) rather than editing by hand.
