from typing import Any, Dict, List, Optional

from port_ocean.context.ocean import ocean

from fake_org_data.fixture_packs import (
    get_fixture_pack_name,
    load_pack_resource,
    persons_for_department,
)
from fake_org_data.generator import generate_fake_persons, generate_fake_projects
from fake_org_data.static import FAKE_OFFICES, FAKE_TEAMS

FAKE_DEPARTMENT_EMPLOYEES = "/department/{department_id}/employees"


def _pack_results_or_none(resource: str) -> Optional[List[Dict[str, Any]]]:
    """If fixturePack is set and pack has `resource`.json, return those rows."""
    pack = get_fixture_pack_name()
    if not pack:
        return None
    return load_pack_resource(pack, resource)


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
        pack = get_fixture_pack_name()
        if pack and load_pack_resource(pack, "persons") is not None:
            results = persons_for_department(pack, department_id, limit)
            return {"results": results}

        result = await generate_fake_persons(
            department_id, limit, entity_kb_size, latency
        )
        return result

    @ocean.router.get("/offices")
    async def get_offices() -> Dict[str, Any]:
        pack_rows = _pack_results_or_none("offices")
        if pack_rows is not None:
            return {"results": pack_rows}
        return {"results": [office.dict() for office in FAKE_OFFICES]}

    @ocean.router.get("/teams")
    async def get_teams() -> Dict[str, Any]:
        pack_rows = _pack_results_or_none("teams")
        if pack_rows is not None:
            return {"results": pack_rows}
        return {"results": [team.dict() for team in FAKE_TEAMS]}

    @ocean.router.get("/projects")
    async def get_projects() -> Dict[str, Any]:
        pack_rows = _pack_results_or_none("projects")
        if pack_rows is not None:
            return {"results": pack_rows}
        return await generate_fake_projects()
