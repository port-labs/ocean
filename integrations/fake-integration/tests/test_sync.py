import os
from typing import Any
from unittest.mock import AsyncMock

from port_ocean.tests.helpers.ocean_app import (
    get_raw_result_on_integration_sync_resource_config,
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


def assert_on_results(results: Any, kind: str) -> None:
    assert len(results) > 0
    entities, errors = results
    assert len(errors) == 0
    assert len(entities) > 0
    if kind == "fake-person":
        assert entities[0] == FAKE_PERSON_RAW
    else:
        assert len(entities) == 5


async def test_full_sync_with_http_mock(
    get_mocked_ocean_app: Any,
    get_mock_ocean_resource_configs: Any,
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

    app = get_mocked_ocean_app()
    resource_configs = get_mock_ocean_resource_configs()

    for resource_config in resource_configs:
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )

        assert_on_results(results, resource_config.kind)


async def test_full_sync_using_mocked_3rd_party(
    monkeypatch: Any,
    get_mocked_ocean_app: Any,
    get_mock_ocean_resource_configs: Any,
) -> None:
    fake_client_mock = AsyncMock()
    fake_client_mock.return_value = [FakePerson(**FAKE_PERSON_RAW)]

    monkeypatch.setattr(fake_client, "get_fake_persons", fake_client_mock)

    app = get_mocked_ocean_app()
    resource_configs = get_mock_ocean_resource_configs()

    for resource_config in resource_configs:
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )

        assert_on_results(results, resource_config.kind)
