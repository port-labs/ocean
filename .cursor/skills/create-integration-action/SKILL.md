---
name: create-integration-action
description: |
  Add an integration action to an existing Ocean integration, so Port can invoke work in a
  third-party system (dispatch a workflow, trigger a pipeline, launch an agent) and track the
  run's progress and outcome. Use when asked to add an action, add a self-service action to an
  integration, make an integration trigger or run something, or wire an action's completion
  webhook back to Port.

  Required arguments: integration (e.g. "jenkins", "gitlab-v2") and action name (e.g. "trigger_build")
  Optional arguments: action inputs, whether completion is reported synchronously or by webhook,
    task_id (branch name)
---

# Create Integration Action

Add an action executor to an existing Ocean integration. To build a whole new integration, use
`create-ocean-integration` instead; this skill assumes `integrations/<name>/` already exists.

## Arguments

**Required:**

- `integration` - directory under `integrations/` (e.g. `gitlab-v2`, `github`, `jenkins`)
- `action name` - snake_case, matches Port's action name (e.g. `trigger_pipeline`, `create_agent`)

**Optional:**

- `inputs` - the action's inputs and which are required
- `completion` - `sync` (finishes inside `execute`) or `webhook` (external system reports later)
- `task_id` - branch name

## API surface — copy these signatures exactly

Every client method lives on `ocean.port_client` (mixed in from
`port_ocean/clients/port/mixins/actions_and_workflow_runs.py`). These are the **complete**
signatures. Do not invent parameters — in particular there is **no `status_label` argument on any
of them**, and no status-label concept anywhere in the framework.

```python
async def post_run_log(run, message, level="INFO", should_raise=False) -> None
async def update_run_started(run, link, external_id, extra_output=None) -> None
async def report_run_completed(run, success, message=None, should_raise=False) -> None
async def find_run_by_external_id(external_id) -> IntegrationRun | None
async def patch_run(run, payload, should_raise=True) -> None
def is_run_in_progress(run) -> bool          # sync, not a coroutine
```

Per-kind behavior differences these methods absorb, and where they leak:

| Call                                | `ActionRun`                                   | `WorkflowNodeRun`                          |
| ----------------------------------- | --------------------------------------------- | ------------------------------------------ |
| `post_run_log(level=...)`           | **`level` is dropped** — always a plain log   | honored (`WARNING` sent as `WARN`)         |
| `update_run_started(extra_output=)` | **silently ignored**                          | merged into the run's `output`             |
| `update_run_started` writes         | `link`, `externalRunId`                       | `status`, `externalRunId`, `output`, `links` |
| `report_run_completed(message=)`    | posted as a run log, then status patched      | posted as a run log, then status + result  |

If you need structured output visible for both kinds, put it in the `message`, not
`extra_output`.

## The contract, and where agents get it wrong

Read this before writing code. These are the framework's actual behaviors, several of which
contradict the code's own docstrings and the published docs.

**The manager reports failures. You report success.** `ExecutionManager._execute_run` calls
`report_run_completed(run, success=False, message=..., should_raise=False)` when `execute`
raises, and does nothing at all when `execute` returns. So a sync action must call
`report_run_completed(run, success=True, ...)` itself, and a webhook action must leave the run in
progress for its processor to complete later.

**Never report a failure yourself.** Raise and let the manager report it. Calling
`report_run_completed(success=False)` _and_ raising double-reports.

**Raise `ActionExecutionError` for expected failures.** The manager branches on it:

| Raised                       | Log                       | Message reported to Port         |
| ---------------------------- | ------------------------- | -------------------------------- |
| `ActionExecutionError` (sub) | `WARNING`, no stack trace | your message, verbatim           |
| anything else                | `exception` + stack trace | `Failed to execute run: <msg>`   |

`gitlab-v2` and `azure-devops` still subclass plain `Exception` and therefore get the noisy
branch. Do not copy that; subclass `ActionExecutionError` (as `github` does).

**Always set `WEBHOOK_PROCESSOR_CLASS`.** `register_executor` reads the attribute directly, and
on `AbstractExecutor` it is only a bare annotation with no default. A sync executor that omits it
raises `AttributeError` at registration.

**`AbstractExecutor`'s docstring and `docs/.../features/actions.md` are both stale.** They
mention a `PARTITION_KEY` attribute (the real API is an async `_get_partition_key` method), show
success reported via `patch_run` with `RunStatus.SUCCESS` (use `report_run_completed`), and refer
to `.port/spec.yaml` (every integration with actions uses `.port/spec.json`). Follow this skill,
not those.

**Actions only run under two conditions.** `ocean.py` starts the manager only when
`actions_processor.enabled` **and** `event_listener.should_run_actions` — the latter is `False`
for the `WEBHOOKS_ONLY` and `ONCE` listeners. Then
`start_processing_action_runs` returns early unless `port_client.auth.is_machine_user()`. An
action that "does nothing" locally is usually one of these, not a bug in your code.

## Workflow

```
- [ ] Step 1: Locate the integration and choose placement
- [ ] Step 2: Decide sync vs webhook completion
- [ ] Step 3: Bootstrap actions support (first action only)
- [ ] Step 4: Declare the action in .port/spec.json
- [ ] Step 5: Write the executor
- [ ] Step 6: Add exceptions
- [ ] Step 7: Decide on a partition key
- [ ] Step 8: Wire async completion (webhook actions only)
- [ ] Step 9: Register the executor
- [ ] Step 10: Tests
- [ ] Step 11: Release intent and verification
```

### Step 1: Locate the integration and choose placement

Placement follows the integration's existing package topology. Check whether a package
directory named after the product sits next to `main.py`:

| Topology                                              | Actions go in                            | Import as                |
| ----------------------------------------------------- | ---------------------------------------- | ------------------------ |
| Named package (`github/`, `gitlab/`, `azure_devops/`) | `integrations/<name>/<package>/actions/` | `from github.actions...` |
| Flat (`actions/`, `clients/` at integration root)     | `integrations/<name>/actions/`           | `from actions...`        |

Match whichever the integration already uses. Do not introduce a package directory.

`github` groups a family of related actions into a subpackage
(`actions/external_custom_properties/`). Do that only once there are three or more actions
sharing helpers; a lone action goes flat in `actions/`.

### Step 2: Decide sync vs webhook completion

Ask this before writing anything, because it determines what `execute` does at the end.

**Sync** - the third-party call completes the work. `execute` finishes by calling
`report_run_completed(run, success=True, message=...)`. Set `WEBHOOK_PROCESSOR_CLASS = None`.
Example: `github`'s `update_repo_external_custom_properties`.

**Webhook** - the call starts long-running work (a pipeline, a workflow, an agent). `execute`
finishes by calling `update_run_started(...)` and returns with the run still in progress; a
webhook processor completes it later. Example: `gitlab-v2`'s `trigger_pipeline`.

If the third-party system has no completion webhook, the action must be sync. `cursor-cloud-agents`
does exactly this per-input: its `v1` API has no webhooks, so that path completes the run at
launch while `v0` waits for one.

### Step 3: Bootstrap actions support (first action only)

Skip if the integration already has an `actions/` directory. Otherwise create three things.

**A per-integration abstract executor** that owns the client and answers the two rate-limit
questions once, so each action only implements `execute`:

```python
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from <pkg>.clients.client_factory import create_<name>_client

MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE = 20


class Abstract<Name>Executor(AbstractExecutor):
    # `AbstractExecutor` only declares this as an annotation, so a subclass without a
    # webhook would raise AttributeError when `register_executor` reads it. The explicit
    # type keeps mypy happy when a subclass overrides it with a processor class.
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = create_<name>_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        info = self.client.get_rate_limit_status()
        if not info:
            return False
        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        info = self.client.get_rate_limit_status()
        if not info:
            return 0.0
        return info.seconds_until_reset
```

The bare `WEBHOOK_PROCESSOR_CLASS = None` (no annotation) also works at runtime but mypy infers
`None` as the type and rejects every subclass override. Use the annotated form.

If the client exposes no rate-limit information, return `False` and `0.0` — the manager then
never waits (`cursor-cloud-agents` does this and relies on Ocean's retrying transport instead).
Build the client in `__init__` only if that cannot fail; `azure-devops` resolves it lazily behind
a `client` property so the integration still boots when actions are disabled or the config is
unsupported.

**A registry** at `<pkg>/actions/registry.py` (see Step 9).

**`actionsProcessingEnabled`** in `.port/spec.json` (see Step 4). Without it,
`Settings.validate_actions_processor` raises `"Serving as an actions processor is not currently
supported for this integration."` as soon as the actions processor is enabled.

### Step 4: Declare the action in `.port/spec.json`

`ACTION_NAME` must equal `actions[].name` exactly. The manager routes on `run.action_type`, which
resolves to `payload.integrationActionType` for an `ActionRun` and
`config.integrationInvocationType` for a `WorkflowNodeRun` — both carry that spec name. A
mismatch means no executor is found, and the manager acknowledges the run and immediately fails
it with `"No executor registered for action type '<name>'"`.

Input `name` values are camelCase and are the keys you read from `run.execution_properties`.

```json
"actionsProcessingEnabled": true,
"actions": [
  {
    "name": "trigger_pipeline",
    "icon": "GitLab",
    "description": "Trigger a GitLab CI/CD pipeline",
    "inputs": [
      {
        "name": "project",
        "title": "Project",
        "type": "string",
        "description": "Project path or numeric ID",
        "required": true
      },
      {
        "name": "reportPipelineStatus",
        "title": "Report pipeline status",
        "type": "boolean",
        "description": "Whether to report completion status back to Port",
        "default": true
      }
    ]
  }
]
```

For a webhook action, include a boolean opt-in input like `reportPipelineStatus` (default
`true`). The webhook processor honors it, letting a user trigger work without Port waiting on
its outcome. Also confirm `saas.liveEvents.enabled` is `true`.

Input `type` values in use across the existing action specs are `string`, `boolean`, `array`,
and `jqObject` for key-value maps. A `jqObject` description conventionally tells the user they
can reference trigger data with `{{ .trigger.by.user.email }}`; copy that phrasing from
`integrations/github/.port/spec.json`.

### Step 5: Write the executor

One file per action: `<pkg>/actions/<action_name>_executor.py`.

```python
import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from <pkg>.actions.abstract_<name>_executor import Abstract<Name>Executor
from <pkg>.actions.utils import build_external_id
from <pkg>.helpers.exceptions import MissingExecutionPropertyError, TriggerPipelineError
from <pkg>.webhook.constants import WEBHOOK_PATH
from <pkg>.webhook.webhook_processors.trigger_pipeline_webhook_processor import (
    TriggerPipelineWebhookProcessor,
)


class TriggerPipelineExecutor(Abstract<Name>Executor):
    ACTION_NAME = "trigger_pipeline"
    WEBHOOK_PROCESSOR_CLASS = TriggerPipelineWebhookProcessor
    WEBHOOK_PATH = WEBHOOK_PATH

    async def execute(self, run: IntegrationRun) -> None:
        project = run.execution_properties.get("project")
        if not project:
            raise MissingExecutionPropertyError("project is required")

        # Log before handing off, so a failed dispatch still leaves a trace.
        await ocean.port_client.post_run_log(
            run, f"Triggering pipeline for {project}", should_raise=False
        )

        try:
            pipeline = await self.client.trigger_pipeline(project)
        except httpx.HTTPStatusError as e:
            raise TriggerPipelineError.from_response(
                e.response, f"Could not trigger pipeline for '{project}'"
            )

        if not pipeline or not all(k in pipeline for k in ("id", "project_id", "web_url")):
            raise TriggerPipelineError(
                "Failed to trigger pipeline: upstream returned an empty or incomplete response"
            )

        external_id = build_external_id(pipeline["project_id"], pipeline["id"])
        await ocean.port_client.update_run_started(
            run, pipeline["web_url"], external_id
        )
        await ocean.port_client.post_run_log(
            run, f"Pipeline triggered: {pipeline['web_url']}", should_raise=False
        )
        logger.info(
            f"Pipeline {pipeline['id']} triggered for {project}",
            pipeline_id=pipeline["id"],
            external_id=external_id,
        )
```

For a **sync** action, replace the closing `update_run_started` block with:

```python
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Updated {len(updated)} repositories",
        )
```

Notes on the APIs used:

- `run.execution_properties` is the unified accessor for inputs and works for both run kinds.
  Do not reach into `run.payload` or `run.config`.
- `execute` receives `IntegrationRun`, which is either an `ActionRun` or a `WorkflowNodeRun`.
  Write against the unified `ocean.port_client` methods and you never need to branch on the
  kind; they handle the differences. Branch on `run.run_kind` (or
  `isinstance(run, WorkflowNodeRun)`) only if you genuinely need kind-specific behavior — and
  check the leak table above first.
- Pass `should_raise=False` on progress logs. A failed log should not fail the action.
- `update_run_started(run, link, external_id, extra_output=None)` sets the link users click and
  the external id the webhook correlates on. For a `WorkflowNodeRun` it also flips status to
  `IN_PROGRESS` and seeds `run.output`, which `report_run_completed` later preserves — so a
  webhook action should always call it, not just when it has an external id.
- Validate inputs before any network call, and validate the upstream response before reading
  fields out of it.
- Keep detail in the log/`message` text. There is no separate label field.

Use a pydantic model instead of dict access when inputs are structured (nested objects or
lists), following whatever pydantic version the integration already imports. Keep it beside the
executor and give it a `from_execution_properties` classmethod;
`cursor-cloud-agents/actions/request_bodies.py` is the reference for that shape.

### Step 6: Add exceptions

Put exceptions in the integration's existing exceptions module (`<pkg>/helpers/exceptions.py` or
`<pkg>/actions/exceptions.py`). Subclass `ActionExecutionError` so the manager logs them without
a stack trace and reports the message verbatim:

```python
from port_ocean.exceptions.execution_manager import ActionExecutionError


class MissingExecutionPropertyError(ActionExecutionError):
    """Raised when a required execution property is absent from the action run."""


class TriggerPipelineError(ActionExecutionError):
    """Raised when the API returns an error while triggering a pipeline."""

    @classmethod
    def from_response(cls, response: httpx.Response, prefix: str) -> "TriggerPipelineError":
        return cls(f"{prefix}: {cls._response_detail(response)}")

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
        except Exception:
            body = None

        if isinstance(body, dict):
            for key in ("error_description", "message", "error"):
                if (value := body.get(key)) is not None:
                    return value if isinstance(value, str) else json.dumps(value)

        text = response.text.strip()
        return text or f"HTTP {response.status_code}"
```

`from_response` is a per-integration helper, not framework code — copy it in, adjusting the key
preference order to the upstream API's error envelope. Existing versions:
`integrations/gitlab-v2/gitlab/helpers/exceptions.py` and
`integrations/azure-devops/azure_devops/actions/exceptions.py`.

The point of it is that raw `httpx.HTTPStatusError` messages are useless to the user who
triggered the action; the upstream error body is what they need.

### Step 7: Decide on a partition key

Override `_get_partition_key` on the executor to return a string when two concurrent runs of
this action would conflict, or `None` (the inherited default) to let them run in parallel. Runs
sharing a key are queued together and executed sequentially.

```python
    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        return f"{org}/{repo}"
```

Return `None` when the inputs needed to build the key are missing, rather than raising —
`_poll_action_runs` calls this before `execute`, and an exception there logs and drops the run
without ever reporting a failure to Port. `github`'s `dispatch_workflow` also returns `None`
whenever the config makes serialization unnecessary, so the common path stays parallel.

Reach for a key when the action mutates one resource (`update_repo_external_custom_properties`
partitions on `org/repo`) or when correlation depends on ordering (legacy
`dispatch_workflow` tracking polls for "the most recent run", which only works one at a time).

### Step 8: Wire async completion (webhook actions only)

The executor writes an external id; the webhook processor rebuilds it and finds the run.
Getting this correlation right is the subtle part of an async action.

See [async-completion.md](async-completion.md) for the external-id convention, a full action
webhook processor, and how action processors differ from catalog processors.

### Step 9: Register the executor

Registration is explicit — nothing scans the `actions/` directory. Add to
`<pkg>/actions/registry.py`:

```python
from port_ocean.context.ocean import ocean

from <pkg>.actions.trigger_pipeline_executor import TriggerPipelineExecutor


def register_actions_executors() -> None:
    """Register all actions executors."""
    ocean.register_action_executor(TriggerPipelineExecutor())
```

Call it from the integration's `main.py` at module level, after webhook registration:

```python
register_actions_executors()
```

Instantiating the executor happens at import time, so anything expensive or failure-prone in
`__init__` breaks integration startup — see the lazy-client note in Step 3.

Registering two executors with the same `ACTION_NAME` raises `DuplicateActionExecutorError`.

### Step 10: Tests

Add a test file mirroring the executor's path, plus one for the webhook processor if you added
one. See [testing.md](testing.md) for the mocking approach, which is unusual enough to be worth
copying exactly: tests patch the `ocean` object _on the module under test_, not globally.

Cover: happy path asserting the exact `update_run_started` or `report_run_completed` call, each
missing required input, an upstream HTTP error, and a malformed upstream response. Add a
`_get_partition_key` test if you overrode it, including the missing-input case returning `None`.

### Step 11: Release intent and verification

Add `integrations/<name>/.ocean-release/<unique-name>.yaml`:

```yaml
bump: minor
changelog-type: feature
changelog: Added a trigger_pipeline action that triggers a pipeline and reports its outcome
```

`bump` is `patch`, `minor`, or `major`; `changelog-type` is one of `breaking`, `deprecation`,
`feature`, `improvement`, `bugfix`, `doc`. A new action is normally `minor` / `feature`. Do not
edit `CHANGELOG.md` or `pyproject.toml` — a separate `[IntegrationBump]` PR applies them from
this file.

Then verify from the integration directory:

```bash
cd integrations/<name>
make test
make lint
```

## Checklist

**Contract:**

- [ ] Sync action calls `report_run_completed(success=True, ...)`; webhook action does not
- [ ] Failures are raised, never self-reported
- [ ] `WEBHOOK_PROCESSOR_CLASS` is set (annotated `| None = None` on the abstract executor)
- [ ] No invented client-method arguments — signatures match the API surface table

**Wiring:**

- [ ] `ACTION_NAME` matches `actions[].name` in `.port/spec.json`
- [ ] Input keys read from `run.execution_properties` match the spec's camelCase input names
- [ ] `actionsProcessingEnabled: true` present in `.port/spec.json`
- [ ] Executor registered in `registry.py` and called from `main.py`
- [ ] Executor placed to match the integration's existing package topology
- [ ] `__init__` cannot fail at import time, or the client is resolved lazily

**Async completion:**

- [ ] External id built by a shared helper used by both executor and processor
- [ ] Processor returns `WebhookProcessorType.ACTION` and `[]` from `get_matching_kinds`
- [ ] Processor checks `is_run_in_progress` and the opt-in input before completing
- [ ] Processor only acts on terminal external statuses

**Quality:**

- [ ] Inputs validated before any network call; upstream response validated before use
- [ ] Exceptions subclass `ActionExecutionError`; HTTP errors go through `from_response`
- [ ] `_get_partition_key` returns `None` rather than raising on missing inputs
- [ ] Tests cover happy path, each missing input, upstream error, malformed response
- [ ] Release intent file added; `make test` and `make lint` pass

## Reference

- [async-completion.md](async-completion.md) - external id correlation and action webhook processors
- [testing.md](testing.md) - fixtures and mocking for executors and action webhook processors
- Framework: `port_ocean/core/handlers/actions/abstract_executor.py`,
  `port_ocean/core/handlers/actions/execution_manager.py`
- Client facade: `port_ocean/clients/port/mixins/actions_and_workflow_runs.py`
- Run models (`execution_properties`, `action_type`, `is_in_progress`): `port_ocean/core/models.py`
- Simplest end-to-end webhook example: `integrations/gitlab-v2/gitlab/actions/trigger_pipeline_executor.py`
- Simplest sync example: `integrations/github/github/actions/external_custom_properties/update_repo_external_custom_properties_executor.py`
- Most complex example (polling, partition key, dual tracking modes):
  `integrations/github/github/actions/dispatch_workflow_executor.py`
- Framework docs: `docs/framework-guides/docs/framework/features/actions.md` (stale — see the
  contract section)
