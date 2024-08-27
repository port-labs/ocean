import os
from typing import Any, Dict, List, cast

from pytest_httpx import HTTPXMock

from port_ocean.ocean import Ocean
from port_ocean.tests.helpers import (
    get_integation_resource_config_by_name,
    get_integration_app,
)

USER_AGENT = "Ocean Framework Dummy Integration (https://github.com/port-labs/ocean)"


DUMMY_INTEGRATION_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../integrations/dummy-integration")
)


def get_dummy_integration_app() -> Ocean:
    return get_integration_app(DUMMY_INTEGRATION_PATH)


async def test_dummy_integration_static_kind() -> None:
    app = get_dummy_integration_app()

    category_resource_config = get_integation_resource_config_by_name(
        DUMMY_INTEGRATION_PATH, "dummy-category"
    )

    assert category_resource_config is not None

    result = await app.integration._get_resource_raw_results(category_resource_config)

    assert result is not None
    assert len(result[0]) == 4
    actual_result = cast(List[Dict[str, str]], result[0])
    assert [x["id"] for x in actual_result] == ["sport", "pirate", "dad", "camp"]


async def test_dummy_integration_dynamic_kind_with_http_requests(
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

    app = get_dummy_integration_app()

    joke_resource_config = get_integation_resource_config_by_name(
        DUMMY_INTEGRATION_PATH, "dummy-joke"
    )

    assert joke_resource_config is not None

    result = await app.integration._get_resource_raw_results(joke_resource_config)
    assert result is not None
    assert len(result[0]) == 4
    actual_result = cast(List[Dict[str, Any]], result[0])
    assert actual_result[0]["id"] == "ZOMG"
    assert actual_result[0]["text"] == "hello hungry, I'm dad"
