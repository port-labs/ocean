import os
from typing import Any
from unittest.mock import AsyncMock

from port_ocean.tests.helpers import (
    get_raw_result_on_integration_sync_kinds,
)
from pytest_httpx import HTTPXMock

from fake_org_data import fake_client
from fake_org_data.types import FakeDepartment, FakePerson, FakePersonStatus

USER_AGENT = "Ocean Framework Fake Integration (https://github.com/port-labs/ocean)"

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

FAKE_PERSON = FakePerson(
    id="ZOMG",
    email="test@zomg.io",
    age=42,
    name="Joe McToast",
    status=FakePersonStatus.NOPE,
    department=FakeDepartment(id="hr", name="hr"),
)

FAKE_PERSON_RAW = FAKE_PERSON.dict()


async def test_full_sync_with_http_mock(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        match_headers={"User-Agent": USER_AGENT},
        json={
            "results": [
                FAKE_PERSON_RAW,
            ]
        },
    )

    results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    assert len(results) > 0

    assert "fake-person" in results
    assert "fake-department" in results

    person_results = results["fake-person"]
    department_results = results["fake-department"]

    assert len(person_results) > 0
    assert len(person_results[0][0]) > 1
    assert len(person_results[0][1]) == 0

    assert len(department_results) > 0
    assert len(department_results[0][0]) == 5
    assert len(department_results[0][1]) == 0


async def test_full_sync_using_mocked_3rd_party(monkeypatch: Any) -> None:
    fake_client_mock = AsyncMock()
    fake_client_mock.return_value = [FakePerson(**FAKE_PERSON_RAW)]

    monkeypatch.setattr(fake_client, "get_fake_persons", fake_client_mock)

    results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    assert len(results) > 0

    assert "fake-person" in results
    assert "fake-department" in results

    person_results = results["fake-person"]
    department_results = results["fake-department"]

    assert len(person_results) > 0
    assert len(person_results[0][0]) == 5
    assert len(person_results[0][1]) == 0

    assert len(department_results) > 0
    assert len(department_results[0][0]) == 5
    assert len(department_results[0][1]) == 0
