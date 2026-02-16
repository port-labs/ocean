from typing import Any, Literal
import httpx
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.mixins.actions import ActionsClientMixin
from port_ocean.clients.port.mixins.workflow_nodes import WorkflowNodesClientMixin
from port_ocean.core.models import (
    ActionRun,
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

    def _is_wf_node_run(self, run: ActionRun | WorkflowNodeRun) -> bool:
        return isinstance(run, WorkflowNodeRun)

    async def claim_pending_runs(
        self, limit: int, visibility_timeout_ms: int
    ) -> list[ActionRun | WorkflowNodeRun]:
        runs: list[ActionRun | WorkflowNodeRun]
        if self._poll_wf_node:
            runs = list(
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

    async def acknowledge_run(self, run: ActionRun | WorkflowNodeRun) -> None:
        if self._is_wf_node_run(run):
            await self.acknowledge_wf_node_run(run.id)
        else:
            await self.acknowledge_action_run(run.id)

    async def post_run_log(
        self,
        run: ActionRun | WorkflowNodeRun,
        message: str,
        level: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = "INFO",
        should_raise: bool = False,
    ) -> None:
        if self._is_wf_node_run(run):
            # API expects "WARN" not "WARNING"
            log_level = "WARN" if level == "WARNING" else level
            await self.patch_wf_node_run(
                run.id,
                {"logs": [{"logLevel": log_level, "log": message, "tags": {}}]},
                should_raise=should_raise,
            )
        else:
            await self.post_action_run_log(run.id, message)

    async def report_run_failure(
        self,
        run: ActionRun | WorkflowNodeRun,
        error_summary: str,
        should_raise: bool = False,
    ) -> None:
        if self._is_wf_node_run(run):
            await self.patch_wf_node_run(
                run.id,
                {
                    "status": WorkflowNodeRunStatus.COMPLETED,
                    "result": WorkflowNodeRunResult.FAILED,
                    "logs": [{"logLevel": "ERROR", "log": error_summary, "tags": {}}],
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

    async def find_run_by_external_id(self, external_id: str) -> ActionRun | None:
        """Get an action run by its external ID."""
        return await self.get_run_by_external_id(external_id)

    def is_run_in_progress(self, run: ActionRun | WorkflowNodeRun) -> bool:
        """Check if a run is currently in progress."""
        if self._is_wf_node_run(run):
            return run.status == WorkflowNodeRunStatus.IN_PROGRESS
        return run.status == RunStatus.IN_PROGRESS

    async def update_run_started(
        self,
        run: ActionRun | WorkflowNodeRun,
        link: str,
        external_id: str,
        extra_output: dict[str, Any] | None = None,
    ) -> None:
        """Update a run to indicate it has started with a link and external ID."""
        if self._is_wf_node_run(run):
            output: dict[str, Any] = {
                "workflowRunUrl": link,
                "externalRunId": external_id,
            }
            if extra_output:
                output.update(extra_output)
            await self.patch_wf_node_run(
                run.id,
                {
                    "status": WorkflowNodeRunStatus.IN_PROGRESS,
                    "output": output,
                },
            )
        else:
            await self.patch_run(
                run.id,
                {"link": link, "externalRunId": external_id},
            )

    async def report_run_completed(
        self,
        run: ActionRun | WorkflowNodeRun,
        success: bool,
        message: str | None = None,
    ) -> None:
        """Report a run as completed with success or failure."""
        if self._is_wf_node_run(run):
            result = (
                WorkflowNodeRunResult.SUCCESS
                if success
                else WorkflowNodeRunResult.FAILED
            )
            payload: dict[str, Any] = {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": result,
            }
            if message:
                payload["logs"] = [
                    {
                        "logLevel": "INFO" if success else "ERROR",
                        "log": message,
                        "tags": {},
                    }
                ]
            await self.patch_wf_node_run(run.id, payload)
        else:
            status = RunStatus.SUCCESS if success else RunStatus.FAILURE
            await self.patch_run(run.id, {"status": status})
