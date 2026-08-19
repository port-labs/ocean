import os
import inspect
from typing import Any, AsyncGenerator, Dict, List
from port_ocean.tests.helpers.ocean_app import (
    get_raw_result_on_integration_sync_resource_config,
)
from pytest_httpx import HTTPXMock

from fake_org_data import fake_client
from fake_org_data.static import FAKE_OFFICES, FAKE_TEAMS, DEFAULT_PROJECT_COUNT
from fake_org_data.types import FakeDepartment, FakePerson, FakePersonStatus

USER_AGENT = "Ocean Framework Fake Integration (https://github.com/port-labs/ocean)"

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

FAKE_PERSON = FakePerson(
    id="ZOMG",
    email="test@zomg.io",
    age=42,
    name="Joe McToast",
    bio="ZOMG I've been endorsed for xml!",
    status=FakePersonStatus.NOPE,
    department=FakeDepartment(id="hr", name="hr"),
)

FAKE_PERSON_RAW = FAKE_PERSON.dict()


async def assert_on_results(results: Any, kind: str) -> None:
    assert len(results) > 0
    resync_results, errors = results
    if inspect.isasyncgen(resync_results[0]):
        async for entities in resync_results[0]:
            await assert_on_results((entities, errors), kind)
            return
    entities = resync_results
    assert len(entities) > 0
    if kind == "fake-person":
        assert entities[0] == FAKE_PERSON_RAW
    elif kind == "fake-department":
        assert len(entities) == 5
    elif kind == "fake-office":
        assert len(entities) == len(FAKE_OFFICES)
    elif kind == "fake-team":
        assert len(entities) == len(FAKE_TEAMS)
    elif kind == "fake-project":
        assert len(entities) == DEFAULT_PROJECT_COUNT


async def test_full_sync_with_http_mock(
    get_mocked_ocean_app: Any,
    get_mock_ocean_resource_configs: Any,
    httpx_mock: HTTPXMock,
) -> None:
    return
    httpx_mock.add_response(
        match_headers={"User-Agent": USER_AGENT},
        json={
            "results": [
                FAKE_PERSON_RAW,
            ]
        },
    )

    app = get_mocked_ocean_app()
    resource_configs = get_mock_ocean_resource_configs()

    for resource_config in resource_configs:
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )

        await assert_on_results(results, resource_config.kind)


async def mock_fake_person() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    yield [FakePerson(**FAKE_PERSON_RAW).dict()]


async def mock_fake_office() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    yield [office.dict() for office in FAKE_OFFICES]


async def mock_fake_team() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    yield [team.dict() for team in FAKE_TEAMS]


async def mock_fake_project() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    from fake_org_data.generator import generate_fake_projects

    payload = await generate_fake_projects()
    yield payload["results"]


async def test_full_sync_using_mocked_3rd_party(
    monkeypatch: Any,
    get_mocked_ocean_app: Any,
    get_mock_ocean_resource_configs: Any,
) -> None:
    monkeypatch.setattr(fake_client, "get_fake_persons", mock_fake_person)
    monkeypatch.setattr(fake_client, "get_offices", mock_fake_office)
    monkeypatch.setattr(fake_client, "get_teams", mock_fake_team)
    monkeypatch.setattr(fake_client, "get_projects", mock_fake_project)

    app = get_mocked_ocean_app()
    resource_configs = get_mock_ocean_resource_configs()

    for resource_config in resource_configs:
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )

        await assert_on_results(results, resource_config.kind)
