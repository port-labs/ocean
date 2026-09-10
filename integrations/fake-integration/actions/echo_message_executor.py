from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from actions.abstract_fake_executor import AbstractFakeExecutor
from actions.constants import ECHOING_STATUS_LABEL, MESSAGE_ECHOED_STATUS_LABEL
from actions.exceptions import MissingExecutionPropertyError


class EchoMessageExecutor(AbstractFakeExecutor):
    ACTION_NAME = "echo_message"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        message = run.execution_properties.get("message")
        if not message:
            raise MissingExecutionPropertyError("message is required")

        await ocean.port_client.post_run_log(
            run,
            f"Echoing message: {message}",
            status_label=ECHOING_STATUS_LABEL,
            should_raise=False,
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Echo: {message}",
            status_label=MESSAGE_ECHOED_STATUS_LABEL,
        )
