# Async completion via webhook

For an action whose work outlives `execute`, the executor starts the work and records an
**external id**; a webhook processor later rebuilds that id, finds the Port run, and completes
it. Correlation is the part worth getting right.

## The external id convention

Define one helper in `<pkg>/actions/utils.py` and use it from both sides. If the two sides ever
build the id differently, the webhook silently never finds its run.

```python
def build_external_id(project_id: int | str, pipeline_id: int | str) -> str:
    return f"gl_{project_id}_{pipeline_id}"
```

Pick a prefix and the smallest set of ids that uniquely identify the external run, using only
fields present in *both* the trigger response and the webhook payload:

| Integration  | Format                                       | Helper signature                      |
| ------------ | -------------------------------------------- | ------------------------------------- |
| GitLab       | `gl_{project_id}_{pipeline_id}`              | `(project_id, pipeline_id)`           |
| GitHub       | `gh_{owner_id}_{repo_id}_{workflow_run_id}`  | `(workflow_run: dict)`                |
| Azure DevOps | `ado_{project_id}_{pipeline_id}_{run_id}`    | `(project_id, pipeline_id, run_id)`   |

Prefer numeric ids over names, which users can rename mid-run.

The executor writes it with `update_run_started(run, link, external_id, ...)`. The processor
reads it back with `await ocean.port_client.find_run_by_external_id(external_id)`, which
returns an `IntegrationRun | None` — it checks action runs first, then workflow node runs, so
one lookup covers both kinds.

## How action processors differ from catalog processors

An action processor concludes a Port run. A catalog processor upserts entities. The framework
routes them differently: `processor_manager` invokes `ACTION` processors with
`resource_config=None` and skips the kind and mapping lookup entirely, so an action processor
works without anything configured in `port-app-config`.

|                       | Catalog processor                             | Action processor                          |
| --------------------- | --------------------------------------------- | ----------------------------------------- |
| `get_processor_type`  | `WebhookProcessorType.WEBHOOK` (base default) | must return `WebhookProcessorType.ACTION` |
| `get_matching_kinds`  | real kinds                                    | `[]`                                      |
| `resource_config` arg | resolved config                               | `None` — never read it                    |
| Returns               | entities to upsert or delete                  | empty `WebhookEventRawResults`            |

An integration can have two processors for the same external event: one catalog processor that
syncs the pipeline entity, and one action processor that completes the Port run. Azure DevOps
does exactly this with `PipelineRunWebhookProcessor` and `PipelineRunActionWebhookProcessor`.

## Full example

From `integrations/gitlab-v2/gitlab/webhook/webhook_processors/trigger_pipeline_webhook_processor.py`.
Note the four guards in `handle_event`, each of which prevents a real failure mode.

```python
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.actions.utils import build_external_id
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)

TERMINAL_PIPELINE_STATUSES = frozenset({"success", "failed", "canceled", "skipped"})


class TriggerPipelineWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["pipeline"]
    hooks = ["Pipeline Hook"]

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not await super().should_process_event(event):
            return False
        status = event.payload.get("object_attributes", {}).get("status")
        return status in TERMINAL_PIPELINE_STATUSES

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        empty = WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        project_id = payload.get("project", {}).get("id")
        pipeline_id = payload.get("object_attributes", {}).get("id")
        status = payload.get("object_attributes", {}).get("status")

        run = await ocean.port_client.find_run_by_external_id(
            build_external_id(project_id, pipeline_id)
        )

        # 1. Not triggered by Port at all.
        if run is None:
            logger.debug(f"No Port run found for pipeline {pipeline_id}, skipping")
            return empty

        # 2. The user opted out of status reporting.
        if not run.execution_properties.get("reportPipelineStatus", True):
            logger.info(f"reportPipelineStatus disabled for run {run.id}, skipping")
            return empty

        # 3. A duplicate or retried webhook for an already-finished run.
        if not ocean.port_client.is_run_in_progress(run):
            logger.info(f"Run {run.id} already completed, skipping duplicate webhook")
            return empty

        success = status == "success"
        await ocean.port_client.post_run_log(
            run, f"Pipeline completed with status: {status}", should_raise=False
        )
        await ocean.port_client.report_run_completed(
            run, success, f"Pipeline completed: {status}"
        )
        return empty
```

`report_run_completed(run, success, message=None, should_raise=False)` is the whole signature —
`success` is positional here and there is no label argument. The raw upstream status belongs in
the `message`, since that is the only text the user sees.

The fourth guard is `should_process_event` filtering to terminal statuses, so in-progress
events never conclude a run. Prefer an explicit terminal-status set over "not running": a status
you have not seen before then leaves the run in progress instead of concluding it wrongly.

Deriving `success` deserves care. `status == "success"` is right for GitLab because every other
terminal status is a genuine failure. Where the upstream has a "neutral" or "cancelled" terminal
state, decide explicitly which of those should fail the Port run and encode it as a set rather
than a negation:

```python
SUCCESSFUL_STATUSES = frozenset({"success", "skipped"})
...
success = status in SUCCESSFUL_STATUSES
```

## Known race

If the webhook arrives before `update_run_started` finishes writing the external id, the lookup
misses and the run stays in progress until it times out. The window is one Port API round trip.
Every existing integration accepts this rather than adding retry machinery — do the same, and
keep the `run is None` branch a debug log rather than an error.

## Registration

Setting `WEBHOOK_PROCESSOR_CLASS` and `WEBHOOK_PATH` on the executor is what registers the
processor: `register_executor` forwards them to `webhook_manager.register_processor`. Do not
also register it in the integration's catalog webhook registry, or it runs twice.

`WEBHOOK_PATH` is normally the integration's existing webhook path constant (usually
`"/webhook"`), reused so the third-party system needs only one configured endpoint. Use a
static path string; dynamically built paths are not matched by the Redis live-events consumer,
which silently acknowledges and drops the event.
