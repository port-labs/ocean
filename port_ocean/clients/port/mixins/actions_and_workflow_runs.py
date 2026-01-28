from typing import Any, Literal
import httpx
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.mixins.actions import ActionsClientMixin
from port_ocean.clients.port.mixins.workflow_nodes import WorkflowNodesClientMixin
from port_ocean.core.models import (
    BaseRun,
    WorkflowNodeRun,
    RunStatus,
    WorkflowNodeRunStatus,
    WorkflowNodeRunResult,
)


class ActionsAndWorkflowRunsClientMixin(ActionsClientMixin, WorkflowNodesClientMixin):
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        ActionsClientMixin.__init__(self, auth, client)
        WorkflowNodesClientMixin.__init__(self, auth, client)

    def _is_wf_node_run(self, run: BaseRun) -> bool:
        return isinstance(run, WorkflowNodeRun)

    async def acknowledge_base_run(self, run: BaseRun) -> None:
        if self._is_wf_node_run(run):
            await self.acknowledge_wf_node_run(run.id)
        else:
            await self.acknowledge_run(run.id)

    async def post_base_run_log(
        self,
        run: BaseRun,
        message: str,
        level: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = "INFO",
        should_raise: bool = False,
    ) -> None:
        if self._is_wf_node_run(run):
            await self.patch_wf_node_run(
                run.id,
                {"logs": [{"logLevel": level, "message": message, "tags": []}]},
                should_raise=should_raise,
            )
        else:
            await self.post_run_log(run.id, message)

    async def report_base_run_failure(
        self,
        run: BaseRun,
        error_summary: str,
        should_raise: bool = False,
    ) -> None:
        if self._is_wf_node_run(run):
            await self.patch_wf_node_run(
                run.id,
                {
                    "status": WorkflowNodeRunStatus.COMPLETED,
                    "result": WorkflowNodeRunResult.FAILED,
                    "logs": [
                        {"logLevel": "ERROR", "message": error_summary, "tags": []}
                    ],
                },
                should_raise=should_raise,
            )
        else:
            await self.patch_run(
                run.id,
                {
                    "summary": error_summary,
                    "status": RunStatus.FAILURE,
                },
                should_raise=should_raise,
            )
