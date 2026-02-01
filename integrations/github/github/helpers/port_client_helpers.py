"""
Helper functions for unified handling of Port action runs and workflow node runs.
"""

from port_ocean.clients.port.client import PortClient
from port_ocean.core.models import (
    ActionRun,
    WorkflowNodeRun,
    RunStatus,
    WorkflowNodeRunStatus,
    WorkflowNodeRunResult,
)

SUCCESSFUL_CONCLUSIONS = ("success", "skipped", "neutral")


def is_port_wf_run(run: ActionRun | WorkflowNodeRun) -> bool:
    return isinstance(run, WorkflowNodeRun)


async def get_run_by_external_id(
    port_client: PortClient, external_id: str
) -> ActionRun | WorkflowNodeRun | None:
    action_run = await port_client.get_run_by_external_id(external_id)
    if action_run:
        return action_run
    return await port_client.get_wf_node_run_by_external_id(external_id)


def is_run_in_progress(run: ActionRun | WorkflowNodeRun) -> bool:
    if is_port_wf_run(run):
        return run.status == WorkflowNodeRunStatus.IN_PROGRESS
    return run.status == RunStatus.IN_PROGRESS


async def update_run_workflow_started(
    port_client: PortClient,
    run: ActionRun | WorkflowNodeRun,
    workflow_url: str,
    external_id: str,
    workflow_run_id: int,
) -> None:
    if is_port_wf_run(run):
        await port_client.patch_wf_node_run(
            run.id,
            {
                "status": WorkflowNodeRunStatus.IN_PROGRESS,
                "output": {
                    "workflowRunUrl": workflow_url,
                    "externalRunId": external_id,
                    "workflowRunId": workflow_run_id,
                },
            },
        )
    else:
        await port_client.patch_run(
            run.id,
            {"link": workflow_url, "externalRunId": external_id},
        )


async def report_run_workflow_completed(
    port_client: PortClient, run: ActionRun | WorkflowNodeRun, conclusion: str
) -> None:
    is_success = conclusion in SUCCESSFUL_CONCLUSIONS
    if is_port_wf_run(run):
        result = (
            WorkflowNodeRunResult.SUCCESS
            if is_success
            else WorkflowNodeRunResult.FAILED
        )
        await port_client.patch_wf_node_run(
            run.id,
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": result,
                "logs": [
                    {
                        "logLevel": "INFO" if is_success else "ERROR",
                        "message": f"Workflow completed: {conclusion}",
                        "tags": ["workflow_completion"],
                    }
                ],
            },
        )
    else:
        status = RunStatus.SUCCESS if is_success else RunStatus.FAILURE
        await port_client.patch_run(run.id, {"status": status})
