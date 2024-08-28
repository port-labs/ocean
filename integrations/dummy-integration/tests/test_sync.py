import os
from unittest.mock import AsyncMock

from port_ocean.tests.helpers import get_raw_result_on_integration_sync_kinds
from pytest_httpx import HTTPXMock

from punny import pun_client

from punny.types import Pun, PunCategory

USER_AGENT = "Ocean Framework Dummy Integration (https://github.com/port-labs/ocean)"

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))


async def test_full_sync_with_http_mock(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        match_headers={"User-Agent": USER_AGENT},
        json={
            "results": [
                {
                    "id": "ZOMG",
                    "joke": "hello hungry, I'm dad",
                }
            ]
        },
    )

    results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    assert len(results) > 0

    assert 'dummy-joke' in results
    assert 'dummy-category' in results

    joke_results = results['dummy-joke']
    category_results = results['dummy-category']

    assert len(joke_results) > 0
    assert len(joke_results[0][0]) == 4
    assert len(joke_results[0][1]) == 0

    assert len(category_results) > 0
    assert len(category_results[0][0]) == 4
    assert len(category_results[0][1]) == 0


async def test_full_sync_using_mocked_3rd_party(monkeypatch) -> None:
    pun_client_mock = AsyncMock()
    pun_client_mock.return_value = [Pun(
        id='pun_id',
        name='ZOMG',
        funny='YAAS',
        score=3,
        category=PunCategory(id='WAT', name='WAT'),
        text='A pytest entered a bar, foo went out'
    )]

    monkeypatch.setattr(pun_client, 'get_puns', pun_client_mock)

    results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    assert len(results) > 0

    assert 'dummy-joke' in results
    assert 'dummy-category' in results

    joke_results = results['dummy-joke']
    category_results = results['dummy-category']

    assert len(joke_results) > 0
    assert len(joke_results[0][0]) == 4
    assert len(joke_results[0][1]) == 0

    assert len(category_results) > 0
    assert len(category_results[0][0]) == 4
    assert len(category_results[0][1]) == 0
