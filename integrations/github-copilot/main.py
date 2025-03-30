from typing import Any
from enum import StrEnum

from port_ocean.context.ocean import ocean

class ObjectKind(StrEnum):
    COPILOT_TEAM_METRICS = "copilot-team-metrics"
    COPILOT_ORGANIZATION_METRICS = "copilot-organization-metrics"

# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync(ObjectKind.COPILOT_TEAM_METRICS)
async def on_resync_copilot_team_metrics(kind: str) -> list[dict[Any, Any]]:
    # 1. Get all data from the source system
    # 2. Return a list of dictionaries with the raw data of the state to run the core logic of the framework for
    # Example:
    # if kind == "project":
    #     return [{"some_project_key": "someProjectValue", ...}]
    # if kind == "issues":
    #     return [{"some_issue_key": "someIssueValue", ...}]

    # Initial stub to show complete flow, replace this with your own logic
    if kind == "github-copilot-example-kind":
        return [
            {
                "my_custom_id": f"id_{x}",
                "my_custom_text": f"very long text with {x} in it",
                "my_special_score": x * 32 % 3,
                "my_component": f"component-{x}",
                "my_service": f"service-{x %2}",
                "my_enum": "VALID" if x % 2 == 0 else "FAILED",
            }
            for x in range(25)
        ]

    return []

@ocean.on_resync(ObjectKind.COPILOT_ORGANIZATION_METRICS)
async def on_resync_copilot_organization_metrics(kind: str) -> list[dict[Any, Any]]:
    if kind == "github-copilot-example-kind":
        return [
            {
                "my_custom_id": f"id_{x}",
                "my_custom_text": f"very long text with {x} in it",
                "my_special_score": x * 32 % 3,
                "my_component": f"component-{x}",
                "my_service": f"service-{x %2}",
                "my_enum": "VALID" if x % 2 == 0 else "FAILED",
            }
            for x in range(25)
        ]

    return []

# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting github-copilot integration")
