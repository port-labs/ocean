from typing import Any

from port_ocean.core.models import IntegrationRun, WorkflowNodeRun


def set_issue_run_output(run: IntegrationRun, issue: dict[str, Any]) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {
            "identifier": issue["identifier"],
            "issueId": str(issue["id"]),
            "issueUrl": issue.get("url") or "",
        }
