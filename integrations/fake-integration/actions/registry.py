from port_ocean.context.ocean import ocean

from actions.echo_message_executor import EchoMessageExecutor
from actions.trigger_fake_task_executor import TriggerFakeTaskExecutor


def register_action_executors() -> None:
    ocean.register_action_executor(EchoMessageExecutor())
    ocean.register_action_executor(TriggerFakeTaskExecutor())
