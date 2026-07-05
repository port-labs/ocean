from typing import Any, Literal

import httpx
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.mixins.actions import ActionsClientMixin
from port_ocean.clients.port.mixins.workflow_nodes import WorkflowNodesClientMixin
from port_ocean.core.models import (
    IntegrationRun,
    RunStatus,
    WorkflowNodeRun,
    WorkflowNodeRunLog,
    WorkflowNodeRunResult,
    WorkflowNodeRunStatus,
)


class ActionsAndWorkflowRunsClientMixin(ActionsClientMixin, WorkflowNodesClientMixin):
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        ActionsClientMixin.__init__(self, auth, client)
        WorkflowNodesClientMixin.__init__(self, auth, client)
        self._claim_workflow_first: bool = False

    @staticmethod
    def _wf_node_completion_patch(
        result: WorkflowNodeRunResult,
        output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        patch: dict[str, Any] = {
            "status": WorkflowNodeRunStatus.COMPLETED,
            "result": result,
        }
        if output:
            patch["output"] = output
        return patch

    async def claim_pending_runs(
        self,
        limit: int,
        visibility_timeout_ms: int,
        exclude_action_identifiers: list[str] | None = None,
        exclude_workflow_invocation_types: list[str] | None = None,
    ) -> list[IntegrationRun]:
        remaining = limit
        runs: list[IntegrationRun] = []
        for workflow in (self._claim_workflow_first, not self._claim_workflow_first):
            if remaining <= 0:
                break
            if workflow:
                claimed: list[IntegrationRun] = list(
                    await self.claim_pending_wf_node_runs(
                        limit=remaining,
                        visibility_timeout_ms=visibility_timeout_ms,
                        exclude_invocation_types=exclude_workflow_invocation_types,
                    )
                )
            else:
                claimed = list(
                    await self.claim_pending_action_runs(
                        limit=remaining,
                        visibility_timeout_ms=visibility_timeout_ms,
                        exclude_action_identifiers=exclude_action_identifiers,
                    )
                )
            runs.extend(claimed)
            remaining -= len(claimed)
        self._claim_workflow_first = not self._claim_workflow_first
        return runs

    async def acknowledge_run(self, run: IntegrationRun) -> None:
        if isinstance(run, WorkflowNodeRun):
            await self.acknowledge_wf_node_run(run.id)
        else:
            await self.acknowledge_action_run(run.id)

    async def post_run_log(
        self,
        run: IntegrationRun,
        message: str,
        level: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = "INFO",
        should_raise: bool = False,
    ) -> None:
        if isinstance(run, WorkflowNodeRun):
            # API expects "WARN" not "WARNING"
            log_level: Literal["INFO", "WARN", "ERROR", "DEBUG"] = (
                "WARN" if level == "WARNING" else level
            )
            await self.post_wf_node_run_logs(
                run.id,
                [WorkflowNodeRunLog(level=log_level, message=message)],
                should_raise=should_raise,
            )
        else:
            await self.post_action_run_log(run.id, message)

    async def post_run_logs(
        self,
        run: IntegrationRun,
        logs: list[WorkflowNodeRunLog],
        should_raise: bool = False,
    ) -> None:
        if isinstance(run, WorkflowNodeRun):
            await self.post_wf_node_run_logs(run.id, logs, should_raise=should_raise)
        else:
            for log in logs:
                await self.post_action_run_log(run.id, log.message)

    async def patch_run(
        self,
        run: IntegrationRun,
        payload: dict[str, Any],
        should_raise: bool = True,
    ) -> None:
        """Patch an action or workflow node run."""
        if isinstance(run, WorkflowNodeRun):
            await self.patch_wf_node_run(run.id, payload, should_raise=should_raise)
        else:
            await self.patch_action_run(run.id, payload, should_raise=should_raise)

    async def find_run_by_external_id(self, external_id: str) -> IntegrationRun | None:
        """Get a run by its external ID."""
        try:
            action_run = await self.get_run_by_external_id(external_id)
        except Exception:
            action_run = None
        if action_run is not None:
            return action_run
        return await self.get_wf_node_run_by_external_id(external_id)

    def is_run_in_progress(self, run: IntegrationRun) -> bool:
        """Check if a run is currently in progress."""
        return run.is_in_progress

    async def update_run_started(
        self,
        run: IntegrationRun,
        link: str,
        external_id: str,
        extra_output: dict[str, Any] | None = None,
    ) -> None:
        """Update a run to indicate it has started, setting the link and external ID."""
        if isinstance(run, WorkflowNodeRun):
            output: dict[str, Any] = {"workflowRunUrl": link}
            if extra_output:
                output.update(extra_output)
            await self.patch_wf_node_run(
                run.id,
                {
                    "status": WorkflowNodeRunStatus.IN_PROGRESS,
                    "externalRunId": external_id,
                    "output": output,
                },
            )
            run.output = output
        else:
            await self.patch_action_run(
                run.id, {"link": link, "externalRunId": external_id}
            )

    async def report_run_completed(
        self,
        run: IntegrationRun,
        success: bool,
        message: str | None = None,
        should_raise: bool = False,
    ) -> None:
        """Report a run as completed with success or failure."""
        if isinstance(run, WorkflowNodeRun):
            result = (
                WorkflowNodeRunResult.SUCCESS
                if success
                else WorkflowNodeRunResult.FAILED
            )
            if message:
                log_level: Literal["INFO", "WARN", "ERROR", "DEBUG"] = (
                    "INFO" if success else "ERROR"
                )
                await self.post_wf_node_run_logs(
                    run.id,
                    [WorkflowNodeRunLog(level=log_level, message=message)],
                    should_raise=should_raise,
                )
            await self.patch_wf_node_run(
                run.id,
                self._wf_node_completion_patch(result, run.output),
                should_raise=should_raise,
            )
        else:
            status = RunStatus.SUCCESS if success else RunStatus.FAILURE
            if message:
                await self.post_action_run_log(run.id, message)
            await self.patch_action_run(
                run.id, {"status": status}, should_raise=should_raise
            )
