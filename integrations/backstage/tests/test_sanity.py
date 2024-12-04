import os
from typing import Any, Dict


INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


def generate_mock_component(
    name: str = "test-component",
    namespace: str = "default",
    component_type: str = "service",
    lifecycle: str = "production",
    owner: str = "user:default/testuser",
    system: str = "test-system",
) -> Dict[str, Any]:
    return {
        "kind": "Component",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "title": f"{name.capitalize()} Component",
            "description": f"A {component_type} component",
            "labels": {"team": f"{name}-team"},
            "annotations": {"backstage.io/techdocs-ref": "dir:."},
            "links": [{"url": "https://example.com", "title": "Example"}],
            "tags": [component_type, lifecycle],
        },
        "spec": {
            "type": component_type,
            "lifecycle": lifecycle,
            "owner": owner,
            "system": system,
        },
        "relations": [
            {"type": "ownedBy", "targetRef": owner},
            {"type": "partOf", "targetRef": f"system:{namespace}/{system}"},
        ],
    }


def assert_on_results(results: Any, kind: str) -> None:
    assert len(results) > 0
    entities, errors = results
    assert len(errors) == 0
    assert len(entities) > 0
    if kind == "component":
        assert entities[0]["kind"] == "Component"
        assert "metadata" in entities[0]
        assert "spec" in entities[0]
    else:
        assert False, f"Unexpected kind: {kind}"


# TODO: this test is blocked on ocean integration config not being mocked
# async def test_component_sync_with_http_mock(
#     get_mocked_ocean_app: Any,
#     get_mock_ocean_resource_configs: Any,
#     httpx_mock: HTTPXMock,
# ) -> None:
#     mock_component = generate_mock_component()
#     mock_integration_config = {
#         "backstage_token": "test",
#         "backstage_host": "http://localhost:3000",
#     }
#     httpx_mock.add_response(
#         json={
#             "items": [mock_component],
#             "totalItems": 1,
#             "pageInfo": {"hasNextPage": False},
#         },
#     )


#     app: Ocean = get_mocked_ocean_app(mock_integration_config)

#     resource_configs = get_mock_ocean_resource_configs()

#     for resource_config in resource_configs:
#         if resource_config.kind == "component":
#             results = await get_raw_result_on_integration_sync_resource_config(
#                 app, resource_config
#             )
#             assert_on_results(results, resource_config.kind)
