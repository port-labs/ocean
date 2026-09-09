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

## The client facade

Everything Port-facing goes through `ocean.port_client`. The action methods are mixed in from
`port_ocean/clients/port/mixins/actions_and_workflow_runs.py` — a short file, and the source of
truth for their current signatures. Read it before writing `execute`; the framework docstrings
and `docs/framework-guides/docs/framework/features/actions.md` predate it and still describe an
older API.

| Method                                  | What it is for                                             |
| --------------------------------------- | ---------------------------------------------------------- |
| `post_run_log(run, message, ...)`       | progress visible to whoever triggered the action            |
| `update_run_started(run, link, ext_id)` | hand off to long-running external work; run stays open      |
| `report_run_completed(run, success, …)` | conclude a run                                              |
| `find_run_by_external_id(ext_id)`       | webhook side of the correlation; checks both run kinds      |
| `is_run_in_progress(run)`               | guard against duplicate completions (this one is sync)      |
| `patch_run(run, payload)`               | escape hatch for anything the above do not cover            |

These methods absorb the difference between an `ActionRun` and a `WorkflowNodeRun`. Two places
where the absorption is partial, worth knowing before you rely on either:

| Behavior                            | `ActionRun`                              | `WorkflowNodeRun`                 |
| ----------------------------------- | ---------------------------------------- | --------------------------------- |
| `post_run_log(level=...)`           | logged without the level                 | honored (`WARNING` sent as `WARN`) |
| `update_run_started(extra_output=)` | not persisted                            | merged into the run's `output`    |

So when structured detail must reach both kinds, put it in the log or completion `message`.

## The contract

Read this before writing code. These are the framework's actual behaviors, verified in
`port_ocean/core/handlers/actions/execution_manager.py`; a couple of them contradict the
docstrings in `abstract_executor.py`.

**The manager reports failures. You report success.** `ExecutionManager._execute_run` calls
`report_run_completed(run, success=False, message=..., should_raise=False)` when `execute`
raises, and does nothing at all when `execute` returns. So a sync action reports its own success,
and a webhook action leaves the run in progress for its processor to complete later.

**Signal failure by raising.** The manager owns the failure report — one raise produces exactly
one completion.

**Raise `ActionExecutionError` for expected failures.** The manager branches on it:

| Raised                       | Log                       | Message reported to Port       |
| ---------------------------- | ------------------------- | ------------------------------ |
| `ActionExecutionError` (sub) | `WARNING`, no stack trace | your message, verbatim         |
| anything else                | `exception` + stack trace | `Failed to execute run: <msg>` |

`github` uses the first branch. `gitlab-v2` and `azure-devops` still subclass plain `Exception`
and land in the second; prefer `ActionExecutionError` for anything a user can cause.

**Set `WEBHOOK_PROCESSOR_CLASS` on every executor.** `register_executor` reads the attribute
directly, and on `AbstractExecutor` it is a bare annotation with no default, so registration
raises `AttributeError` when it is absent. Sync executors set it to `None`; Step 3 puts that
default on the per-integration base class once.

**Actions run under two conditions.** `ocean.py` starts the manager when
`actions_processor.enabled` **and** `event_listener.should_run_actions` — the latter is `True`
for the default listeners and `False` for `WEBHOOKS_ONLY` and `ONCE`. Then
`start_processing_action_runs` proceeds once `port_client.auth.is_machine_user()` holds. An
action that appears inert locally is usually one of these two conditions rather than a code bug.

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

Match whichever the integration already uses.

`github` groups a family of related actions into a subpackage
(`actions/external_custom_properties/`), which pays off once several actions share helpers. A
lone action sits flat in `actions/`.

### Step 2: Decide sync vs webhook completion

Settle this before writing anything, because it determines what `execute` does at the end.

**Sync** - the third-party call completes the work. `execute` finishes by calling
`report_run_completed(run, success=True, message=...)`, and `WEBHOOK_PROCESSOR_CLASS` stays
`None`. Example: `github`'s `update_repo_external_custom_properties`.

**Webhook** - the call starts long-running work (a pipeline, a workflow, an agent). `execute`
finishes by calling `update_run_started(...)` and returns with the run still in progress; a
webhook processor completes it later. Example: `gitlab-v2`'s `trigger_pipeline`.

Sync is the right shape whenever the third-party system has no completion webhook.
`cursor-cloud-agents` decides this per-input: its `v1` API has no webhooks, so that path
completes the run at launch, while `v0` waits for one.

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
    # `AbstractExecutor` declares this as an annotation only, so subclasses without a
    # webhook rely on this default when `register_executor` reads it. The explicit type
    # keeps mypy happy when a subclass overrides it with a processor class.
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

The annotation on `WEBHOOK_PROCESSOR_CLASS` matters: a bare `= None` makes mypy infer the type as
`None` and reject subclass overrides.

Where the client exposes no rate-limit information, returning `False` and `0.0` lets the manager
proceed immediately — `cursor-cloud-agents` does this and leans on Ocean's retrying transport
instead. Build the client in `__init__` when that is safe; `azure-devops` resolves it lazily
behind a `client` property so the integration still boots when actions are disabled or the
config is unsupported.

**A registry** at `<pkg>/actions/registry.py` (see Step 9).

**`actionsProcessingEnabled`** in `.port/spec.json` (see Step 4).
`Settings.validate_actions_processor` requires it as soon as the actions processor is enabled,
raising `"Serving as an actions processor is not currently supported for this integration."`
otherwise.

### Step 4: Declare the action in `.port/spec.json`

`ACTION_NAME` matches `actions[].name` exactly. The manager routes on `run.action_type`, which
resolves to `payload.integrationActionType` for an `ActionRun` and
`config.integrationInvocationType` for a `WorkflowNodeRun` — both carry that spec name. When the
two drift apart, the manager acknowledges the run and fails it with `"No executor registered for
action type '<name>'"`, which is the signature to look for.

Input `name` values are camelCase and are the keys read from `run.execution_properties`.

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

Input `type` values across the existing action specs are `string`, `boolean`, `array`, and
`jqObject` for key-value maps. Compare a few specs (`github`, `azure-devops`,
`cursor-cloud-agents`) to pick descriptions in house style — `jqObject` descriptions
conventionally tell the user they can reference trigger data with
`{{ .trigger.by.user.email }}`.

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

For a **sync** action, the closing `update_run_started` block becomes:

```python
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Updated {len(updated)} repositories",
        )
```

Notes on the shape above:

- `run.execution_properties` is the unified accessor for inputs and works for both run kinds.
- `execute` receives `IntegrationRun`, which is either an `ActionRun` or a `WorkflowNodeRun`.
  Written against the unified `ocean.port_client` methods, the executor stays kind-agnostic.
  `run.run_kind` (or `isinstance(run, WorkflowNodeRun)`) is there for behavior that genuinely
  differs per kind — check the partial-absorption table above first, since it covers the two
  cases that usually prompt the question.
- `should_raise=False` on progress logs keeps a failed log from failing the action.
- `update_run_started(run, link, external_id, extra_output=None)` sets the link users click and
  the external id the webhook correlates on. For a `WorkflowNodeRun` it also flips status to
  `IN_PROGRESS` and seeds `run.output`, which `report_run_completed` later preserves — so a
  webhook action calls it on every path, including one where the external id is synthetic.
- Validate inputs before any network call, and validate the upstream response before reading
  fields out of it.
- The log and completion `message` carry all the detail a user sees, so spend the words there.

A pydantic model beats dict access once inputs are structured (nested objects or lists),
following whatever pydantic version the integration already imports. Keep it beside the executor
and give it a `from_execution_properties` classmethod;
`cursor-cloud-agents/actions/request_bodies.py` is the reference for that shape.

### Step 6: Add exceptions

Put exceptions in the integration's existing exceptions module (`<pkg>/helpers/exceptions.py` or
`<pkg>/actions/exceptions.py`). Subclassing `ActionExecutionError` gets them logged without a
stack trace and reported verbatim:

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

`from_response` is a per-integration helper rather than framework code, so copy it in and adjust
the key preference order to the upstream API's error envelope. Existing versions:
`integrations/gitlab-v2/gitlab/helpers/exceptions.py` and
`integrations/azure-devops/azure_devops/actions/exceptions.py`.

Its purpose: a raw `httpx.HTTPStatusError` message tells the user who triggered the action
nothing, while the upstream error body tells them what to fix.

### Step 7: Decide on a partition key

Override `_get_partition_key` on the executor to return a string when two concurrent runs of
this action would conflict. Runs sharing a key are queued together and executed sequentially;
the inherited default returns `None`, which lets them run in parallel.

```python
    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        return f"{org}/{repo}"
```

Return `None` when the inputs needed to build the key are missing. This method runs inside
`_poll_action_runs`, before `execute` and outside the try/except that reports failures, so
`None` keeps the run flowing to the executor where a missing input becomes a proper reported
error. `github`'s `dispatch_workflow` also returns `None` whenever its config makes
serialization unnecessary, keeping the common path parallel.

A key earns its place when the action mutates one resource
(`update_repo_external_custom_properties` partitions on `org/repo`) or when correlation depends
on ordering (legacy `dispatch_workflow` tracking polls for "the most recent run", which holds
only one at a time).

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

Executors are instantiated at import time, so keep `__init__` cheap and safe — see the
lazy-client note in Step 3. Two executors sharing an `ACTION_NAME` raise
`DuplicateActionExecutorError` at registration.

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
`feature`, `improvement`, `bugfix`, `doc`. A new action is normally `minor` / `feature`. This
file is the whole release deliverable — a separate `[IntegrationBump]` PR reads it and applies
`CHANGELOG.md` and `pyproject.toml`.

Then verify from the integration directory:

```bash
cd integrations/<name>
make test
make lint
```

## Checklist

**Contract:**

- [ ] Sync action calls `report_run_completed(success=True, ...)`; webhook action leaves it open
- [ ] Failures reach Port by raising
- [ ] `WEBHOOK_PROCESSOR_CLASS` is set (annotated `| None = None` on the abstract executor)
- [ ] Client-method arguments match the facade in `actions_and_workflow_runs.py`

**Wiring:**

- [ ] `ACTION_NAME` matches `actions[].name` in `.port/spec.json`
- [ ] Input keys read from `run.execution_properties` match the spec's camelCase input names
- [ ] `actionsProcessingEnabled: true` present in `.port/spec.json`
- [ ] Executor registered in `registry.py` and called from `main.py`
- [ ] Executor placed to match the integration's existing package topology
- [ ] `__init__` is safe at import time, or the client is resolved lazily

**Async completion:**

- [ ] External id built by a shared helper used by both executor and processor
- [ ] Processor returns `WebhookProcessorType.ACTION` and `[]` from `get_matching_kinds`
- [ ] Processor checks `is_run_in_progress` and the opt-in input before completing
- [ ] Processor only acts on terminal external statuses

**Quality:**

- [ ] Inputs validated before any network call; upstream response validated before use
- [ ] Exceptions subclass `ActionExecutionError`; HTTP errors go through `from_response`
- [ ] `_get_partition_key` returns `None` when its inputs are missing
- [ ] Tests cover happy path, each missing input, upstream error, malformed response
- [ ] Release intent file added; `make test` and `make lint` pass

## Reference

Read the framework source when a detail here does not match what you find — it is the authority,
and this skill trails it.

- [async-completion.md](async-completion.md) - external id correlation and action webhook processors
- [testing.md](testing.md) - fixtures and mocking for executors and action webhook processors
- Client facade: `port_ocean/clients/port/mixins/actions_and_workflow_runs.py`
- Framework: `port_ocean/core/handlers/actions/abstract_executor.py`,
  `port_ocean/core/handlers/actions/execution_manager.py`
- Run models (`execution_properties`, `action_type`, `is_in_progress`): `port_ocean/core/models.py`
- Simplest end-to-end webhook example: `integrations/gitlab-v2/gitlab/actions/trigger_pipeline_executor.py`
- Simplest sync example: `integrations/github/github/actions/external_custom_properties/update_repo_external_custom_properties_executor.py`
- Richest example (polling, partition key, dual tracking modes):
  `integrations/github/github/actions/dispatch_workflow_executor.py`
- Framework docs: `docs/framework-guides/docs/framework/features/actions.md` — predates the
  current client facade, so treat the source as authoritative where they disagree
