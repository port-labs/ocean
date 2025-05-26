from enum import StrEnum, IntEnum
from typing import List, Tuple, Dict, Any, AsyncGenerator

from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean

from .types import FakePerson
from .static import FAKE_DEPARTMENTS


API_URL = "http://localhost:8000/integration/department"
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


async def get_fake_persons_batch(
    department_id: str, limit: int, entity_kb_size: int, latency_ms: int
) -> List[Dict[Any, Any]]:
    url = f"{API_URL}/{department_id}/employees?limit={limit}&entity_kb_size={entity_kb_size}&latency={latency_ms}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

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


async def get_fake_persons() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    batches, entity_kb_size, latency_ms = get_config()
    async for departments_batch in get_departments():
        for department in departments_batch:
            for batch in batches:
                current_result = await get_fake_persons_batch(
                    department["id"], batch, entity_kb_size, latency_ms
                )
                yield current_result


async def get_random_person_from_batch() -> Dict[Any, Any]:
    async for persons_batch in get_fake_persons():
        return persons_batch[0]
    return {}


async def get_departments() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    single_department_run = ocean.integration_config.get(
        FakeIntegrationConfigKeys.SINGLE_PERF_RUN, False
    )

    departments = (
        FAKE_DEPARTMENTS if not single_department_run else [FAKE_DEPARTMENTS[0]]
    )

    yield [department.dict() for department in departments]
