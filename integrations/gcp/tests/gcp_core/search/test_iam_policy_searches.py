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
EXTRA_PROJECT_FIELD = "__project"


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


def test_expand_bindings_into_member_entities() -> None:
    from gcp_core.search.iam_policies import expand_iam_policy_bindings

    scope = _project_scope()
    entities = expand_iam_policy_bindings(
        [
            {
                "resource": "//cloudresourcemanager.googleapis.com/projects/my-project",
                "asset_type": "cloudresourcemanager.googleapis.com/Project",
                "project": "projects/123456789",
                "folders": ["folders/111"],
                "organization": "organizations/222",
                "policy": {
                    "bindings": [
                        {
                            "role": "roles/viewer",
                            "members": [
                                "serviceAccount:app@my-project.iam.gserviceaccount.com",
                                "allUsers",
                            ],
                        },
                        {
                            "role": "roles/owner",
                            "members": ["user:alex@example.com"],
                            "condition": {
                                "expression": "request.time < timestamp('2026-01-01T00:00:00Z')",
                                "title": "until",
                                "description": "",
                                "location": "",
                            },
                        },
                        {"role": "", "members": ["user:ignored@example.com"]},
                        {"role": "roles/editor", "members": []},
                    ]
                },
            }
        ],
        scope,
    )

    assert [entity["member"] for entity in entities] == [
        "serviceAccount:app@my-project.iam.gserviceaccount.com",
        "allUsers",
        "user:alex@example.com",
    ]
    assert entities[0]["member_type"] == "serviceAccount"
    assert entities[0]["role"] == "roles/viewer"
    assert entities[0]["condition"] is None
    assert entities[0][EXTRA_PROJECT_FIELD] == scope
    assert entities[2]["condition"]["expression"].startswith("request.time")
    assert entities[2]["member_id"] == "alex@example.com"


@pytest.mark.asyncio
async def test_search_uses_search_all_iam_policies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import iam_policies

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
        del client, rate_limiter, timeout
        captured.append(
            {"method": method, "request": dict(request), "page_size": page_size}
        )
        monkeypatch.setattr(
            "gcp_core.utils.parse_protobuf_messages", lambda results: results
        )
        yield parse_fn(
            MagicMock(
                results=[
                    {
                        "resource": "//compute.googleapis.com/projects/my-project/zones/z/instances/vm",
                        "asset_type": "compute.googleapis.com/Instance",
                        "project": "projects/123",
                        "policy": {
                            "bindings": [
                                {
                                    "role": "roles/compute.viewer",
                                    "members": [
                                        f"serviceAccount:sa-{index}@example.com"
                                        for index in range(101)
                                    ],
                                }
                            ]
                        },
                    }
                ]
            )
        )

    monkeypatch.setattr(iam_policies, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(iam_policies, "get_asset_client", lambda: MagicMock())

    batches: list[list[dict[str, Any]]] = []
    async for batch in iam_policies._search_project(
        _project_scope(),
        BoundedSemaphore(1),
        ["compute.googleapis.com/Instance", "iam.googleapis.com/ServiceAccount"],
        policy_query="memberTypes:serviceAccount",
    ):
        batches.append(batch)

    assert captured == [
        {
            "method": "search_all_iam_policies",
            "request": {
                "scope": "projects/my-project",
                "asset_types": [
                    "compute.googleapis.com/Instance",
                    "iam.googleapis.com/ServiceAccount",
                ],
                "query": "memberTypes:serviceAccount",
            },
            "page_size": 500,
        }
    ]
    assert [len(batch) for batch in batches] == [100, 1]
    assert batches[0][0]["role"] == "roles/compute.viewer"


@pytest.mark.asyncio
async def test_search_omits_blank_policy_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import iam_policies

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
        del client, method, parse_fn, rate_limiter, timeout, page_size
        captured.append(dict(request))
        if False:
            yield []

    monkeypatch.setattr(iam_policies, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(iam_policies, "get_asset_client", lambda: MagicMock())

    async for _ in iam_policies._search_project(
        _project_scope(),
        BoundedSemaphore(1),
        ["iam.googleapis.com/ServiceAccount"],
        policy_query=None,
    ):
        pass

    assert "query" not in captured[0]


@pytest.mark.asyncio
async def test_fetch_iterates_projects_and_not_folders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.overrides import GCPPortAppConfig
    from gcp_core.search import iam_policies

    seen: list[list[str]] = []

    async def fake_iterate(
        fn: Any, *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del fn, args
        seen.append(list(kwargs["asset_types"]))
        yield [{"resource": "projects/my-project"}]

    async def unexpected_folders() -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise AssertionError("folder scope must not be searched")
        yield []

    monkeypatch.setattr(
        "gcp_core.search.iterators.iterate_per_available_project", fake_iterate
    )
    monkeypatch.setattr(
        iam_policies,
        "_rate_limit",
        AsyncMock(return_value=(MagicMock(), BoundedSemaphore(1))),
    )
    monkeypatch.setattr(
        "gcp_core.search.resource_searches.search_all_folders", unexpected_folders
    )

    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "iam.googleapis.com/Policy",
                    "selector": {
                        "query": "true",
                        "assetTypes": ["iam.googleapis.com/ServiceAccount"],
                        "policyQuery": "memberTypes:serviceAccount",
                    },
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".member",
                                "blueprint": '"gcpIamPolicyBinding"',
                            }
                        }
                    },
                }
            ]
        }
    )

    batches = [
        batch async for batch in iam_policies.fetch_iam_policies(config.resources[0])
    ]

    assert seen == [["iam.googleapis.com/ServiceAccount"]]
    assert batches == [[{"resource": "projects/my-project"}]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [PermissionDenied("missing permission"), NotFound("project missing")],
)
async def test_search_swallows_permission_and_not_found(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    from gcp_core.search import iam_policies

    async def fake_paginated_query(
        *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise error
        yield []

    monkeypatch.setattr(iam_policies, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(iam_policies, "get_asset_client", lambda: MagicMock())

    batches = [
        batch
        async for batch in iam_policies._search_project(
            _project_scope(),
            BoundedSemaphore(1),
            ["cloudresourcemanager.googleapis.com/Project"],
        )
    ]

    assert batches == []


@pytest.mark.asyncio
async def test_search_reraises_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import iam_policies

    async def fake_paginated_query(
        *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise ValueError("boom")
        yield []

    monkeypatch.setattr(iam_policies, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(iam_policies, "get_asset_client", lambda: MagicMock())

    with pytest.raises(ValueError, match="boom"):
        async for _ in iam_policies._search_project(
            _project_scope(),
            BoundedSemaphore(1),
            ["cloudresourcemanager.googleapis.com/Project"],
        ):
            pass


def test_example_raw_matches_expanded_binding_and_mapping() -> None:
    import jq  # type: ignore[import-not-found]

    from gcp_core.search.iam_policies import expand_iam_policy_bindings

    raw = json.loads((EXAMPLES / "raw.json").read_text())
    expected = json.loads((EXAMPLES / "expected.json").read_text())
    scope = raw[EXTRA_PROJECT_FIELD]
    policies = [
        {
            "resource": raw["resource"],
            "asset_type": raw["asset_type"],
            "project": raw["project"],
            "folders": raw["folders"],
            "organization": raw["organization"],
            "policy": {"bindings": [{"role": raw["role"], "members": [raw["member"]]}]},
        }
    ]

    assert expand_iam_policy_bindings(policies, scope) == [raw]
    mapped = {
        "identifier": jq.compile(
            '.resource + "|" + .role + "|" + .member + "|" + (.condition.expression // "")'
        )
        .input_value(raw)
        .first(),
        "title": jq.compile(".member").input_value(raw).first(),
        "blueprint": jq.compile('"gcpIamPolicyBinding"').input_value(raw).first(),
        "properties": {
            "role": jq.compile(".role").input_value(raw).first(),
            "member": jq.compile(".member").input_value(raw).first(),
            "resource": jq.compile(".resource").input_value(raw).first(),
            "assetType": jq.compile(".asset_type").input_value(raw).first(),
        },
        "relations": {
            "project": jq.compile(".__project.name").input_value(raw).first(),
        },
    }
    assert mapped == expected
