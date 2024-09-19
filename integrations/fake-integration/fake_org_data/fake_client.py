from faker import Faker
from typing import List
from random import randint

from port_ocean.utils import http_async_client

from .types import FakeDepartment, FakePerson


fake = Faker()

API_URL = "http://localhost:8000/integration/department"
USER_AGENT = "Ocean Framework Fake Integration (https://github.com/port-labs/ocean)"


async def get_fake_persons(department: FakeDepartment) -> List[FakePerson]:
    amount = randint(2, 19)
    url = f"{API_URL}/{department.name}/employees/{amount}"
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
                "department": department,
            }
        )
        for person in raw_persons["results"]
    ]
