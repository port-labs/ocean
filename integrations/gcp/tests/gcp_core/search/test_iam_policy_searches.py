import json
from asyncio import BoundedSemaphore
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import port_ocean.context.ocean as ocean_module
import pytest
from google.api_core.exceptions import NotFound, PermissionDenied
from port_ocean.context.ocean import PortOceanContext, initialize_port_ocean_context
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "iam-policy-binding"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    mock_app = MagicMock()
    mock_app.config.integration.config = {"search_all_resources_per_minute_quota": 100}
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)
    yield
    ocean_module._port_ocean = PortOceanContext(None)


def _project_scope() -> dict[str, Any]:
    return {
        "name": "projects/my-project",
        "project_id": "my-project",
        "display_name": "My Project",
    }


def test_iam_policy_search_result_uses_the_list_assets_block() -> None:
    from gcp_core.search.asset_content import iam_policy_search_result_to_asset

    scope = _project_scope()
    asset = iam_policy_search_result_to_asset(
        {
            "resource": "//cloudresourcemanager.googleapis.com/projects/my-project",
            "asset_type": "cloudresourcemanager.googleapis.com/Project",
            "project": "projects/123",
            "folders": ["folders/111"],
            "organization": "organizations/222",
            "policy": {
                "bindings": [
                    {
                        "role": "roles/container.developer",
                        "members": [
                            "serviceAccount:app@my-project.iam.gserviceaccount.com"
                        ],
                    }
                ]
            },
        },
        scope,
        "__project",
    )

    assert asset["name"].startswith("//cloudresourcemanager.googleapis.com/")
    assert asset["iam_policy"]["bindings"][0]["role"] == "roles/container.developer"
    assert "policy" not in asset
    assert asset["__project"] == scope
    assert asset["project"] == "projects/123"


@pytest.mark.asyncio
async def test_default_resource_search_does_not_send_a_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import resource_searches

    captured: list[dict[str, Any]] = []

    async def fake_paginated_query(
        client: Any,
        method: str,
        request: dict[str, Any],
        parse_fn: Any,
        rate_limiter: Any = None,
        timeout: Any = None,
        page_size: int = 100,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del client, parse_fn, rate_limiter, timeout, page_size
        captured.append({"method": method, "request": dict(request)})
        if False:
            yield []

    monkeypatch.setattr(resource_searches, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(resource_searches, "get_asset_client", lambda: MagicMock())

    async for _ in resource_searches.search_all_resources_in_project(
        _project_scope(),
        "compute.googleapis.com/Instance",
        BoundedSemaphore(1),
    ):
        pass

    assert captured[0]["method"] == "search_all_resources"
    assert "query" not in captured[0]["request"]
    assert captured[0]["request"]["asset_types"] == ["compute.googleapis.com/Instance"]


@pytest.mark.asyncio
async def test_resource_search_sends_server_side_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import resource_searches

    captured: list[dict[str, Any]] = []

    async def fake_paginated_query(
        client: Any,
        method: str,
        request: dict[str, Any],
        parse_fn: Any,
        rate_limiter: Any = None,
        timeout: Any = None,
        page_size: int = 100,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del client, parse_fn, rate_limiter, timeout, page_size
        captured.append(dict(request))
        if False:
            yield []

    monkeypatch.setattr(resource_searches, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(resource_searches, "get_asset_client", lambda: MagicMock())

    async for _ in resource_searches.search_all_resources_in_project(
        _project_scope(),
        "compute.googleapis.com/Instance",
        BoundedSemaphore(1),
        search_query="labels.env:prod",
    ):
        pass

    assert captured[0]["query"] == "labels.env:prod"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content_type", "method", "page_size"),
    [
        ("IAM_POLICY", "list_assets", 1000),
        ("ORG_POLICY", "list_assets", 1000),
        ("ACCESS_POLICY", "list_assets", 1000),
        ("OS_INVENTORY", "list_assets", 1000),
        ("RELATIONSHIP", "list_assets", 1000),
    ],
)
async def test_content_type_without_query_uses_list_assets(
    monkeypatch: pytest.MonkeyPatch,
    content_type: str,
    method: str,
    page_size: int,
) -> None:
    from gcp_core.search import asset_content

    captured: list[dict[str, Any]] = []

    async def fake_paginated_query(
        client: Any,
        called_method: str,
        request: dict[str, Any],
        parse_fn: Any,
        rate_limiter: Any = None,
        timeout: Any = None,
        page_size: int = 100,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del client, parse_fn, rate_limiter, timeout
        captured.append(
            {
                "method": called_method,
                "request": dict(request),
                "page_size": page_size,
            }
        )
        if False:
            yield []

    monkeypatch.setattr(asset_content, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(asset_content, "get_asset_client", lambda: MagicMock())

    async for _ in asset_content.fetch_cloud_asset_content_in_scope(
        _project_scope(),
        BoundedSemaphore(1),
        "compute.googleapis.com/Instance",
        content_type,
    ):
        pass

    assert captured[0]["method"] == method
    assert captured[0]["page_size"] == page_size
    assert captured[0]["request"]["content_type"] == content_type
    assert captured[0]["request"]["parent"] == "projects/my-project"
    assert "query" not in captured[0]["request"]


@pytest.mark.asyncio
async def test_iam_policy_query_uses_search_all_iam_policies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import asset_content

    captured: list[dict[str, Any]] = []

    class FakeResponse:
        def __init__(self) -> None:
            self.results = [
                {
                    "resource": "//compute.googleapis.com/projects/my-project/zones/z/instances/vm",
                    "asset_type": "compute.googleapis.com/Instance",
                    "project": "projects/123",
                    "policy": {
                        "bindings": [
                            {
                                "role": "roles/compute.viewer",
                                "members": ["serviceAccount:app@example.com"],
                            }
                        ]
                    },
                }
            ]
            self.next_page_token = ""

    async def fake_paginated_query(
        client: Any,
        method: str,
        request: dict[str, Any],
        parse_fn: Any,
        rate_limiter: Any = None,
        timeout: Any = None,
        page_size: int = 100,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del client, rate_limiter, timeout
        captured.append(
            {"method": method, "request": dict(request), "page_size": page_size}
        )
        response = FakeResponse()
        monkeypatch.setattr(
            asset_content, "parse_protobuf_messages", lambda results: results
        )
        yield parse_fn(response)

    monkeypatch.setattr(asset_content, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(asset_content, "get_asset_client", lambda: MagicMock())

    batches = [
        batch
        async for batch in asset_content.fetch_cloud_asset_content_in_scope(
            _project_scope(),
            BoundedSemaphore(1),
            "compute.googleapis.com/Instance",
            "IAM_POLICY",
            asset_query="memberTypes:serviceAccount",
        )
    ]

    assert captured[0]["method"] == "search_all_iam_policies"
    assert captured[0]["page_size"] == 500
    assert captured[0]["request"]["query"] == "memberTypes:serviceAccount"
    assert captured[0]["request"]["scope"] == "projects/my-project"
    assert batches[0][0]["iam_policy"]["bindings"][0]["role"] == "roles/compute.viewer"
    assert batches[0][0]["__project"]["name"] == "projects/my-project"


@pytest.mark.asyncio
async def test_folder_asset_type_is_not_listed_inside_projects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import asset_content

    seen: list[tuple[str, str]] = []

    async def fake_folders() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"name": "folders/7"}]

    async def fake_fetch(
        scope: dict[str, Any],
        semaphore: BoundedSemaphore,
        asset_type: str,
        content_type: str,
        asset_query: str | None = None,
        rate_limiter: Any = None,
        scope_field: str = "__project",
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del semaphore, asset_query, rate_limiter
        seen.append((scope["name"], scope_field))
        yield [{"asset_type": asset_type, "content_type": content_type}]

    async def unexpected_projects(
        *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del args, kwargs
        raise AssertionError("project iteration must not run for folder asset types")
        yield []

    monkeypatch.setattr(asset_content, "search_all_folders", fake_folders)
    monkeypatch.setattr(asset_content, "fetch_cloud_asset_content_in_scope", fake_fetch)
    monkeypatch.setattr(
        "gcp_core.search.iterators.iterate_per_available_project",
        unexpected_projects,
    )

    batches = [
        batch
        async for batch in asset_content.iter_cloud_asset_content(
            "cloudresourcemanager.googleapis.com/Folder",
            "IAM_POLICY",
            None,
            rate_limiter=MagicMock(),
            semaphore=BoundedSemaphore(1),
        )
    ]

    assert seen == [("folders/7", "__folder")]
    assert batches == [
        [
            {
                "asset_type": "cloudresourcemanager.googleapis.com/Folder",
                "content_type": "IAM_POLICY",
            }
        ]
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [PermissionDenied("missing permission"), NotFound("scope missing")],
)
async def test_content_search_swallows_permission_and_not_found(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    from gcp_core.search import asset_content

    async def fake_paginated_query(
        *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise error
        yield []

    monkeypatch.setattr(asset_content, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(asset_content, "get_asset_client", lambda: MagicMock())

    batches = [
        batch
        async for batch in asset_content.fetch_cloud_asset_content_in_scope(
            _project_scope(),
            BoundedSemaphore(1),
            "compute.googleapis.com/Instance",
            "ORG_POLICY",
        )
    ]

    assert batches == []


@pytest.mark.asyncio
async def test_content_search_reraises_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import asset_content

    async def fake_paginated_query(
        *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise ValueError("boom")
        yield []

    monkeypatch.setattr(asset_content, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(asset_content, "get_asset_client", lambda: MagicMock())

    with pytest.raises(ValueError, match="boom"):
        async for _ in asset_content.fetch_cloud_asset_content_in_scope(
            _project_scope(),
            BoundedSemaphore(1),
            "compute.googleapis.com/Instance",
            "RELATIONSHIP",
        ):
            pass


def test_example_matches_items_to_parse_mapping() -> None:
    import jq  # type: ignore[import-not-found]

    raw = json.loads((EXAMPLES / "raw.json").read_text())
    expected = json.loads((EXAMPLES / "expected.json").read_text())
    binding = raw["iam_policy"]["bindings"][0]
    parsed = {key: value for key, value in raw.items() if key != "iam_policy"}
    parsed["item"] = binding

    mapped = {
        "identifier": jq.compile(
            '.name + "|" + .item.role + "|" + (.item.members | join(","))'
        )
        .input_value(parsed)
        .first(),
        "title": jq.compile(".item.role").input_value(parsed).first(),
        "blueprint": jq.compile('"gcpIamPolicyBinding"').input_value(parsed).first(),
        "properties": {
            "role": jq.compile(".item.role").input_value(parsed).first(),
            "members": jq.compile(".item.members").input_value(parsed).first(),
            "resource": jq.compile(".name").input_value(parsed).first(),
            "assetType": jq.compile(".asset_type").input_value(parsed).first(),
        },
        "relations": {
            "project": jq.compile(".__project.name").input_value(parsed).first(),
        },
    }
    assert mapped == expected
