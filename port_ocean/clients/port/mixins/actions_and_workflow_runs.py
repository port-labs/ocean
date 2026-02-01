from typing import Literal

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
        self._poll_wf_node: bool = False

    def _is_wf_node_run(self, run: BaseRun) -> bool:
        return isinstance(run, WorkflowNodeRun)

    async def claim_pending_runs(
        self, limit: int, visibility_timeout_ms: int
    ) -> list[BaseRun]:
        if self._poll_wf_node:
            runs: list[BaseRun] = list(
                await self.claim_pending_wf_node_runs(
                    limit=limit, visibility_timeout_ms=visibility_timeout_ms
                )
            )
        else:
            runs = list(
                await self.claim_pending_action_runs(
                    limit=limit, visibility_timeout_ms=visibility_timeout_ms
                )
            )
        self._poll_wf_node = not self._poll_wf_node
        return runs

    async def acknowledge_run(self, run: BaseRun) -> None:
        if self._is_wf_node_run(run):
            await self.acknowledge_wf_node_run(run.id)
        else:
            await self.acknowledge_action_run(run.id)

    async def post_run_log(
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
            await self.post_action_run_log(run.id, message)

    async def report_run_failure(
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
