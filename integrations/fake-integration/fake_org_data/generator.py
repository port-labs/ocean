import asyncio
from random import randint
from typing import Any, Dict, Union

from faker import Faker

from .static import FAKE_DEPARTMENTS
from .types import FakePerson, FakePersonStatus

fake = Faker()

DEFAULT_ENTITIES_AMOUNT = 400
DEFAULT_ENTITY_KB_SIZE = 1
DEFAULT_LATENCY_MS = 0


async def generate_fake_persons(
    department_id: Union[str, None],
    amount: int,
    entity_kb_size: int,
    latency: int,
) -> Dict[str, Any]:
    departments = [x for x in FAKE_DEPARTMENTS if x.id == department_id]
    department = (
        departments[0]
        if len(departments)
        else FAKE_DEPARTMENTS[randint(0, len(FAKE_DEPARTMENTS) - 1)]
    )

    company_domain = fake.company_email().split("@")[-1]
    results = []
    for _ in range(amount if amount > 0 else DEFAULT_ENTITIES_AMOUNT):
        results.append(
            FakePerson(
                id=fake.passport_number(),
                name=fake.name(),
                email=fake.email(domain=company_domain),
                age=randint(20, 100),
                department=department,
                bio=fake.text(
                    max_nb_chars=(
                        entity_kb_size if entity_kb_size > 0 else DEFAULT_ENTITY_KB_SIZE
                    )
                    * 1024
                ),
                status=(
                    FakePersonStatus.WORKING
                    if randint(0, 2) % 2 == 0
                    else FakePersonStatus.NOPE
                ),
            ).dict()
        )
    latency_to_use = latency / 1000 if latency > 0 else DEFAULT_LATENCY_MS
    if latency_to_use > 0:
        await asyncio.sleep(latency_to_use)

    return {"results": results}
