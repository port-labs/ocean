from typing import Any, Dict

from fastapi import FastAPI

from fake_org_data.generator import generate_fake_persons
import uvicorn

FAKE_DEPARTMENT_EMPLOYEES = "/integration/department/{department_id}/employees"


def initialize_fake_routes() -> None:
    fastapi_app = FastAPI()
    router = fastapi_app.router
    @router.get(FAKE_DEPARTMENT_EMPLOYEES)
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
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8001)
initialize_fake_routes()
