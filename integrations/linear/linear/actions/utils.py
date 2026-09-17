from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from linear.core.mutations.issue.types import MutationIssue


def set_issue_run_output(run: IntegrationRun, issue: MutationIssue) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {
            "identifier": issue.identifier,
            "issueId": issue.id,
            "issueUrl": issue.url,
        }
