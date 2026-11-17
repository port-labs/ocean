from typing import Any, Dict, Optional

from fastapi import Body
from port_ocean.context.ocean import ocean

from fake_org_data.generator import generate_fake_persons, generate_fake_projects
from fake_org_data.static import FAKE_OFFICES, FAKE_TEAMS

FAKE_DEPARTMENT_EMPLOYEES = "/department/{department_id}/employees"

# Fixture routes for Custom Ocean pagination e2e (relative next_link + body cursor).
RELATIVE_NEXT_LINK_ITEMS = "/pagination/relative-next/items"
BODY_CURSOR_QUERY = "/pagination/body-cursor/query"

_RELATIVE_PAGES: Dict[Optional[str], Dict[str, Any]] = {
    None: {
        "results": [{"id": "rel-1", "name": "Relative Page One"}],
        "_links": {"next": f"{RELATIVE_NEXT_LINK_ITEMS}?cursor=page-2"},
    },
    "page-2": {
        "results": [{"id": "rel-2", "name": "Relative Page Two"}],
    },
}

_BODY_CURSOR_PAGES: Dict[Optional[str], Dict[str, Any]] = {
    None: {
        "data": [{"id": "body-1", "name": "Body Cursor Page One"}],
        "next_page_token": "body-page-2",
        "has_more": True,
    },
    "body-page-2": {
        "data": [{"id": "body-2", "name": "Body Cursor Page Two"}],
        "has_more": False,
    },
}


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

    @ocean.router.get(RELATIVE_NEXT_LINK_ITEMS)
    async def get_relative_next_link_items(
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fixture: returns a relative next-link path for Custom Ocean next_link tests."""
        return _RELATIVE_PAGES.get(cursor, _RELATIVE_PAGES[None])

    @ocean.router.post(BODY_CURSOR_QUERY)
    async def post_body_cursor_query(
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> Dict[str, Any]:
        """Fixture: expects pagination cursor in the JSON body for Custom Ocean tests."""
        token = payload.get("next_page_token")
        return _BODY_CURSOR_PAGES.get(token, _BODY_CURSOR_PAGES[None])
