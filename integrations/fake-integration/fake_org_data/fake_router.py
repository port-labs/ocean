from typing import Any, Dict

from port_ocean.context.ocean import ocean

from fake_org_data.generator import generate_fake_persons


FAKE_ROUTE = "/department/{department_id}/employees/{limit}"


def initialize_fake_routes() -> None:
    @ocean.router.get(FAKE_ROUTE)
    def get_employees_per_department(department_id: str, limit: int) -> Dict[str, Any]:
        return generate_fake_persons(department_id, limit)
