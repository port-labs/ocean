from enum import StrEnum, IntEnum
from typing import List, Tuple, Dict, Any, AsyncGenerator
from uuid import uuid4

from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean

from .types import FakePerson
from .static import FAKE_DEPARTMENTS
from .fixture_packs import get_fixture_pack_name, load_pack_resource

API_URL = "http://localhost:8000/integration"
USER_AGENT = "Ocean Framework Fake Integration (https://github.com/port-labs/ocean)"


class FakeIntegrationDefaults(IntEnum):
    ENTITY_AMOUNT = 20
    ENTITY_KB_SIZE = 1
    THIRD_PARTY_BATCH_SIZE = 1000
    THIRD_PARTY_LATENCY_MS = 0


class FakeIntegrationConfigKeys(StrEnum):
    ENTITY_AMOUNT = "entity_amount"
    ENTITY_KB_SIZE = "entity_kb_size"
    THIRD_PARTY_BATCH_SIZE = "third_party_batch_size"
    THIRD_PARTY_LATENCY_MS = "third_party_latency_ms"
    SINGLE_PERF_RUN = "single_department_run"
    FIXTURE_PACK = "fixture_pack"


def get_config() -> Tuple[List[int], int, int]:
    entity_amount = ocean.integration_config.get(
        FakeIntegrationConfigKeys.ENTITY_AMOUNT,
        FakeIntegrationDefaults.ENTITY_AMOUNT,
    )
    batch_size = ocean.integration_config.get(
        FakeIntegrationConfigKeys.THIRD_PARTY_BATCH_SIZE,
        FakeIntegrationDefaults.THIRD_PARTY_BATCH_SIZE,
    )
    if batch_size < 1:
        batch_size = FakeIntegrationDefaults.THIRD_PARTY_BATCH_SIZE

    entity_kb_size_factor: int = ocean.integration_config.get(
        FakeIntegrationConfigKeys.ENTITY_KB_SIZE,
        FakeIntegrationDefaults.ENTITY_KB_SIZE,
    )
    if entity_kb_size_factor < 1:
        entity_kb_size_factor = FakeIntegrationDefaults.ENTITY_KB_SIZE

    latency_ms = ocean.integration_config.get(
        FakeIntegrationConfigKeys.THIRD_PARTY_LATENCY_MS,
        FakeIntegrationDefaults.THIRD_PARTY_LATENCY_MS,
    )
    if latency_ms < 0:
        latency_ms = FakeIntegrationDefaults.THIRD_PARTY_LATENCY_MS

    batches = [entity_amount]
    if entity_amount > batch_size:
        round_batches = entity_amount // batch_size
        leftover = entity_amount % batch_size

        batches = [batch_size for _ in range(round_batches)]

        if leftover > 0:
            batches += [leftover]

    return batches, entity_kb_size_factor, latency_ms


async def _fetch_integration_results(path: str) -> List[Dict[Any, Any]]:
    url = f"{API_URL}{path}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    response.raise_for_status()
    return response.json()["results"]


async def get_fake_persons_batch(
    department_id: str, limit: int, entity_kb_size: int, latency_ms: int
) -> List[Dict[Any, Any]]:
    url = f"{API_URL}/department/{department_id}/employees?limit={limit}&entity_kb_size={entity_kb_size}&latency={latency_ms}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    response.raise_for_status()

    raw_persons = response.json()

    return [
        FakePerson(
            **{
                **person,
                "department": [
                    department
                    for department in FAKE_DEPARTMENTS
                    if department_id == department.id
                ][0],
            }
        ).dict()
        for person in raw_persons["results"]
    ]


def _person_fetch_plan() -> Tuple[List[int], int, int]:
    """Shared batch plan for fixture packs and loadgen (one code path)."""
    if get_fixture_pack_name():
        # Pack route ignores size/latency; one unrestricted batch per department.
        return [-1], 1, 0
    return get_config()


async def get_fake_persons() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    batches, entity_kb_size, latency_ms = _person_fetch_plan()
    async for departments_batch in get_departments():
        for department in departments_batch:
            for batch in batches:
                current_result = await get_fake_persons_batch(
                    department["id"], batch, entity_kb_size, latency_ms
                )
                if current_result:
                    yield current_result


async def get_random_person_from_batch() -> Dict[Any, Any]:
    async for persons_batch in get_fake_persons():
        return persons_batch[0]
    return {}


async def get_departments() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    single_department_run = ocean.integration_config.get(
        FakeIntegrationConfigKeys.SINGLE_PERF_RUN, False
    )

    pack = get_fixture_pack_name()
    if pack:
        pack_departments = load_pack_resource(pack, "departments")
        if pack_departments is not None:
            departments = (
                pack_departments[:1] if single_department_run else pack_departments
            )
            yield departments
            return

    source = FAKE_DEPARTMENTS if not single_department_run else FAKE_DEPARTMENTS[:1]
    yield [department.dict() for department in source]


async def _results_from_pack_or_fetch(
    resource: str, fetch_path: str
) -> List[Dict[Any, Any]]:
    """Prefer pack JSON for `resource` when fixturePack is set; else HTTP fetch."""
    pack = get_fixture_pack_name()
    if pack:
        rows = load_pack_resource(pack, resource)
        if rows is not None:
            return rows
    return await _fetch_integration_results(fetch_path)


async def get_offices() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    yield await _results_from_pack_or_fetch("offices", "/offices")


async def get_teams() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    yield await _results_from_pack_or_fetch("teams", "/teams")


async def get_projects() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    yield await _results_from_pack_or_fetch("projects", "/projects")


async def trigger_fake_task(task_name: str) -> Dict[str, Any]:
    task_id = str(uuid4())
    return {
        "id": task_id,
        "name": task_name,
        "status": "pending",
        "link": f"/fake-tasks/{task_id}",
    }
