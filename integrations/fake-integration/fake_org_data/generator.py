import asyncio
import base64
from datetime import datetime
import json
from random import randint
from typing import Any, Literal

from faker import Faker
from pydantic import BaseModel
import yaml
from .static import FAKE_DEPARTMENTS
from .types import (
    FakeDepartment,
    FakePerson,
    FakePersonStatus,
    FakeProject,
    FakeRepository,
)

fake = Faker()

DEFAULT_ENTITIES_AMOUNT = 400
DEFAULT_ENTITY_KB_SIZE = 1
DEFAULT_LATENCY_MS = 0
DEFAULT_ITEMS_TO_PARSE_ENTITY_COUNT = 0
DEFAULT_ITEMS_TO_PARSE_ENTITY_SIZE_KB = 1
DEFAULT_FILE_SIZE_KB = 1

existing_fake_people: list[dict[str, Any]] = []


def get_random_department() -> FakeDepartment:
    return FAKE_DEPARTMENTS[randint(0, len(FAKE_DEPARTMENTS) - 1)]


async def generate_fake_persons(
    amount: int,
    entity_kb_size: int,
    latency: int,
    items_to_parse_entity_count: int,
    items_to_parse_entity_size_kb: int,
) -> list[dict[str, Any]]:

    company_domain = fake.company_email().split("@")[-1]
    results: list[dict[str, Any]] = []
    for _ in range(amount if amount > 0 else DEFAULT_ENTITIES_AMOUNT):
        # Generate 2-5 projects per person for itemsToParse testing
        projects = [
            FakeProject(
                id=f"proj-{str(fake.uuid4())}",
                name=fake.catch_phrase(),
                status=fake.random_element(elements=("active", "completed", "pending")),
                description=fake.text(
                    max_nb_chars=(
                        items_to_parse_entity_size_kb
                        if items_to_parse_entity_size_kb > 0
                        else DEFAULT_ITEMS_TO_PARSE_ENTITY_SIZE_KB
                    )
                    * 1024
                ),
            )
            for _ in range(
                items_to_parse_entity_count
                if items_to_parse_entity_count > 0
                else DEFAULT_ITEMS_TO_PARSE_ENTITY_COUNT
            )
        ]

        results.append(
            FakePerson(
                id=fake.passport_number(),
                name=fake.name(),
                email=fake.email(domain=company_domain),
                age=randint(20, 100),
                department=get_random_department(),
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
                projects=projects,
            ).dict()
        )
    if len(existing_fake_people) == 0:
        existing_fake_people.extend(results[:100])
    latency_to_use = latency / 1000 if latency > 0 else DEFAULT_LATENCY_MS
    if latency_to_use > 0:
        await asyncio.sleep(latency_to_use)

    return results


def get_random_fake_person_data() -> dict[str, Any]:
    return existing_fake_people[randint(0, min(99, len(existing_fake_people) - 1))]


def get_random_fake_person() -> FakePerson:
    """Get a random person from existing fake people"""
    if existing_fake_people and len(existing_fake_people) > 0:
        person_data = get_random_fake_person_data()
        return FakePerson(**person_data)
    # Fallback: generate a simple person
    company_domain = fake.company_email().split("@")[-1]
    return FakePerson(
        id=fake.passport_number(),
        name=fake.name(),
        email=fake.email(domain=company_domain),
        age=randint(20, 100),
        department=get_random_department(),
        bio=fake.text(max_nb_chars=DEFAULT_ENTITY_KB_SIZE * 1024),
        status=(
            FakePersonStatus.WORKING
            if randint(0, 2) % 2 == 0
            else FakePersonStatus.NOPE
        ),
    )


def get_random_fake_project() -> FakeProject:
    random_person = get_random_fake_person()
    if random_person.projects and len(random_person.projects) > 0:
        fake_random_project = random_person.projects[
            randint(0, len(random_person.projects) - 1)
        ]
        return fake_random_project
    return FakeProject(
        id=f"proj-{str(fake.uuid4())}",
        name=fake.catch_phrase(),
        status=fake.random_element(elements=("active", "completed", "pending")),
        description=fake.text(max_nb_chars=DEFAULT_ENTITY_KB_SIZE * 1024),
    )


async def generate_fake_codeowners_file(row_count: int, latency: int) -> str:
    if latency > 0:
        await asyncio.sleep(latency / 1000)
    content = "# Codeowners\n"
    for _ in range(row_count):
        content += f"/projects/{get_random_fake_project().id}    @{get_random_fake_person().name}\n"

    return content


async def generate_fake_yaml_file(
    entity_amount: int,
    entity_kb_size: int,
    latency: int,
    items_to_parse_entity_count: int,
    items_to_parse_entity_size_kb: int,
) -> str:
    if latency > 0:
        await asyncio.sleep(latency / 1000)
    persons_data = await generate_fake_persons(
        amount=entity_amount,
        entity_kb_size=entity_kb_size,
        latency=0,
        items_to_parse_entity_count=items_to_parse_entity_count,
        items_to_parse_entity_size_kb=items_to_parse_entity_size_kb,
    )
    yaml_data = yaml.dump(persons_data)
    return yaml_data


async def generate_fake_json_file(
    entity_amount: int,
    entity_kb_size: int,
    latency: int,
    items_to_parse_entity_count: int,
    items_to_parse_entity_size_kb: int,
) -> str:
    if latency > 0:
        await asyncio.sleep(latency / 1000)
    persons_data = await generate_fake_persons(
        amount=entity_amount,
        entity_kb_size=entity_kb_size,
        latency=0,
        items_to_parse_entity_count=items_to_parse_entity_count,
        items_to_parse_entity_size_kb=items_to_parse_entity_size_kb,
    )
    json_data = json.dumps(persons_data)
    return base64.b64encode(json_data.encode()).decode("utf-8")


async def generate_fake_repositories(
    amount: int,
    entity_kb_size: int,
    latency: int,
) -> list[dict[str, Any]]:
    """Generate fake repositories with owners"""
    languages = ["Python", "JavaScript", "TypeScript", "Go", "Java", "Rust", "Ruby"]
    statuses = ["active", "archived", "private", "public"]

    results = []
    for _ in range(amount if amount > 0 else DEFAULT_ENTITIES_AMOUNT):
        # Get a random person to be the owner
        if existing_fake_people:
            owner_data = get_random_fake_person_data()
            owner = FakePerson(**owner_data)
        else:
            # Generate a person if none exist
            company_domain = fake.company_email().split("@")[-1]
            owner = FakePerson(
                id=fake.passport_number(),
                name=fake.name(),
                email=fake.email(domain=company_domain),
                age=randint(20, 100),
                department=get_random_department(),
                bio=fake.text(
                    max_nb_chars=(
                        entity_kb_size * 1024
                        if entity_kb_size > 0
                        else DEFAULT_ENTITY_KB_SIZE * 1024
                    )
                ),
                status=(
                    FakePersonStatus.WORKING
                    if randint(0, 2) % 2 == 0
                    else FakePersonStatus.NOPE
                ),
            )

        repo_name = fake.slug()
        results.append(
            FakeRepository(
                id=f"repo-{str(fake.uuid4())}",
                name=repo_name,
                status=fake.random_element(elements=statuses),
                language=fake.random_element(elements=languages),
                url=f"https://github.com/{owner.name.lower().replace(' ', '-')}/{repo_name}",
                owner=owner,
            ).dict()
        )

    latency_to_use = latency / 1000 if latency > 0 else DEFAULT_LATENCY_MS
    if latency_to_use > 0:
        await asyncio.sleep(latency_to_use)

    return results


class FakeWebhookEvent(BaseModel):
    action: Literal["create", "update", "delete"]
    type: Literal["fake-person", "fake-department", "fake-repository", "fake-file"]
    payload: list[dict[str, Any]]
    timestamp: str


async def generate_fake_webhook_event(
    type: Literal["fake-person", "fake-department", "fake-repository", "fake-file"],
    entity_amount: int,
    entity_kb_size: int,
    latency: int,
    items_to_parse_entity_count: int,
    items_to_parse_entity_size_kb: int,
    webhook_action: Literal["create", "update", "delete"],
) -> dict[str, Any]:
    if type == "fake-person":
        payload = await generate_fake_persons(
            amount=entity_amount,
            entity_kb_size=entity_kb_size,
            latency=0,
            items_to_parse_entity_count=items_to_parse_entity_count,
            items_to_parse_entity_size_kb=items_to_parse_entity_size_kb,
        )
    elif type == "fake-repository":
        payload = await generate_fake_repositories(
            entity_amount, entity_kb_size, latency
        )
    else:
        raise ValueError(f"Invalid type: {type}")
    event = FakeWebhookEvent(
        action=webhook_action,
        type=type,
        payload=payload,
        timestamp=datetime.now().isoformat(),
    )
    return event.dict()
