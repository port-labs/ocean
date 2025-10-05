from typing import Any
from integrations.github.github.clients.client_factory import create_github_client
from port_ocean.core.handlers.actions.abstract_executor import (
    AbstractExecutor,
)

class DispatchWorkflowExecutor(AbstractExecutor):
    def __init__(self):
        self.rest_client = create_github_client()

    def action_name(self) -> str:
        return "dispatch_workflow"

    async def execute(self, payload: dict[str, Any]) -> None:
        pass
