from random import randint
from typing import Any, Dict, Union

from faker import Faker

from .static import FAKE_DEPARTMENTS
from .types import FakePerson, FakePersonStatus

fake = Faker()


def generate_fake_persons(
    department_id: Union[str, None] = None, amount: Union[int, None] = None
) -> Dict[str, Any]:
    departments = [x for x in FAKE_DEPARTMENTS if x.id == department_id]
    department = (
        departments[0]
        if len(departments)
        else FAKE_DEPARTMENTS[randint(0, len(FAKE_DEPARTMENTS))]
    )

    company_domain = fake.company_email().split("@")[-1]
    results = []
    for _ in range(amount or 400):
        results.append(
            FakePerson(
                id=fake.passport_number(),
                name=fake.name(),
                email=fake.email(domain=company_domain),
                age=randint(20, 100),
                department=department,
                status=FakePersonStatus.WORKING
                if randint(0, 2) % 2 == 0
                else FakePersonStatus.NOPE,
            ).dict()
        )

    return {"results": results}
