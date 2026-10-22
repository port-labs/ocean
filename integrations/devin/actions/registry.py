from port_ocean.context.ocean import ocean

from actions.archive_session_executor import ArchiveSessionExecutor
from actions.create_session_executor import CreateSessionExecutor
from actions.send_message_executor import SendMessageExecutor
from actions.terminate_session_executor import TerminateSessionExecutor


def register_action_executors() -> None:
    """Register all action executors."""
    ocean.register_action_executor(CreateSessionExecutor())
    ocean.register_action_executor(SendMessageExecutor())
    ocean.register_action_executor(TerminateSessionExecutor())
    ocean.register_action_executor(ArchiveSessionExecutor())
