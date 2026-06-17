from typing import Any, Dict

from port_ocean.context.ocean import ocean

from fake_org_data.generator import generate_fake_persons, generate_fake_projects
from fake_org_data.static import FAKE_OFFICES, FAKE_TEAMS


FAKE_DEPARTMENT_EMPLOYEES = "/department/{department_id}/employees"


def initialize_fake_routes() -> None:
    @ocean.router.get(FAKE_DEPARTMENT_EMPLOYEES)
    async def get_employees_per_department(
        department_id: str,
        limit: int = -1,
        entity_kb_size: int = -1,
        latency: int = -1,
    ) -> Dict[str, Any]:
        """Get Employees per Department

        Since we grab these numbers from the config,
        we need a way to set the variables and use the default,
        since the config validation will fail for an empty value,
        we add -1 as the default


        """
        result = await generate_fake_persons(
            department_id, limit, entity_kb_size, latency
        )
        return result

    @ocean.router.get("/offices")
    async def get_offices() -> Dict[str, Any]:
        return {"results": [office.dict() for office in FAKE_OFFICES]}

    @ocean.router.get("/teams")
    async def get_teams() -> Dict[str, Any]:
        return {"results": [team.dict() for team in FAKE_TEAMS]}

    @ocean.router.get("/projects")
    async def get_projects() -> Dict[str, Any]:
        return await generate_fake_projects()
