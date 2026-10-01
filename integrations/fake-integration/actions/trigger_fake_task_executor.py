from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from actions.abstract_fake_executor import AbstractFakeExecutor
from actions.constants import TASK_RUNNING_STATUS_LABEL, TRIGGERING_TASK_STATUS_LABEL
from actions.exceptions import MissingExecutionPropertyError, TriggerFakeTaskError
from actions.utils import build_external_id
from fake_org_data.fake_client import trigger_fake_task
from webhook_processors.trigger_fake_task_webhook_processor import (
    TriggerFakeTaskWebhookProcessor,
)


class TriggerFakeTaskExecutor(AbstractFakeExecutor):
    ACTION_NAME = "trigger_fake_task"
    WEBHOOK_PROCESSOR_CLASS = TriggerFakeTaskWebhookProcessor

    async def execute(self, run: IntegrationRun) -> None:
        task_name = run.execution_properties.get("taskName")
        if not task_name:
            raise MissingExecutionPropertyError("taskName is required")

        await ocean.port_client.post_run_log(
            run,
            f"Triggering fake task '{task_name}'",
            status_label=TRIGGERING_TASK_STATUS_LABEL,
            should_raise=False,
        )

        try:
            task = await trigger_fake_task(task_name)
        except Exception as error:
            raise TriggerFakeTaskError(
                f"Could not trigger fake task '{task_name}': {error}"
            ) from error

        if not task or "id" not in task:
            raise TriggerFakeTaskError(
                "Failed to trigger fake task: upstream returned an empty or incomplete response"
            )

        external_id = build_external_id(str(task["id"]))
        link = task.get("link") or f"/fake-tasks/{task['id']}"
        await ocean.port_client.update_run_started(
            run,
            link,
            external_id,
            status_label=TASK_RUNNING_STATUS_LABEL,
        )
        await ocean.port_client.post_run_log(
            run,
            f"Fake task started: {link}",
            status_label=TASK_RUNNING_STATUS_LABEL,
            should_raise=False,
        )
        logger.info(
            "Fake task triggered",
            task_id=task["id"],
            external_id=external_id,
        )
