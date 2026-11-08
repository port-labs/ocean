import json
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

# Status labels for the GitHub `workflow_run.conclusion` values, shown on the
# Port run. Anything unmapped echoes the raw conclusion. Keep every label to
# two words at most so it stays readable in Port's UI.
CONCLUSION_STATUS_LABELS = {
    "success": "Workflow succeeded",
    "failure": "Workflow failed",
    "cancelled": "Workflow cancelled",
    "timed_out": "Workflow timeout",
    "skipped": "Workflow skipped",
    "neutral": "Workflow neutral",
    "action_required": "Action required",
    "stale": "Workflow stale",
}


def build_external_id(workflow_run: dict[str, Any]) -> str:
    return f'gh_{workflow_run["repository"]["owner"]["id"]}_{workflow_run["repository"]["id"]}_{workflow_run["id"]}'


def extract_error_message(response: httpx.Response) -> str:
    """Pull the most useful message out of a GitHub error response.

    GitHub usually answers with ``{"message": ...}``, but proxies and gateways
    can return HTML or plain text, so neither valid JSON nor a dict is
    guaranteed.
    """
    try:
        body = response.json()
    except ValueError:
        body = None

    if isinstance(body, dict):
        message = body.get("message")
        if message:
            return message if isinstance(message, str) else json.dumps(message)

    return response.text.strip() or f"HTTP {response.status_code}"


async def report_workflow_run_conclusion(
    run: IntegrationRun, workflow_run: dict[str, Any]
) -> None:
    """Mark the Port run completed based on a finished GitHub workflow run."""
    conclusion = workflow_run["conclusion"]
    success = conclusion in ("success", "skipped", "neutral")
    logger.info(
        f"Updating run {run.id} with workflow conclusion: {conclusion}",
        run_id=run.id,
        conclusion=conclusion,
    )

    if isinstance(run, WorkflowNodeRun):
        run.output["conclusion"] = conclusion

    await ocean.port_client.report_run_completed(
        run,
        success,
        f"Workflow completed: {conclusion}",
        status_label=CONCLUSION_STATUS_LABELS.get(conclusion, f"Workflow {conclusion}"),
    )
