from enum import StrEnum
from typing import Any

from port_ocean.context.ocean import ocean

class ObjectKind(StrEnum):
   ENTITY = "backstage-entity"


@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    # 1. Get all data from the source system
    # 2. Return a list of dictionaries with the raw data of the state to run the core logic of the framework for
    # Example:
    # if kind == "project":
    #     return [{"some_project_key": "someProjectValue", ...}]
    # if kind == "issues":
    #     return [{"some_issue_key": "someIssueValue", ...}]

    # Initial stub to show complete flow, replace this with your own logic
    if kind == "backstage-example-kind":
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


@ocean.on_start()
async def on_start() -> None:
    print("Starting backstage integration")
