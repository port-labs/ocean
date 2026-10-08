import json
from asyncio import BoundedSemaphore
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import port_ocean.context.ocean as ocean_module
import proto  # type: ignore
import pytest
from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud.asset_v1.types.assets import IamPolicySearchResult
from google.iam.v1.policy_pb2 import Binding, Policy  # type: ignore
from google.type.expr_pb2 import Expr  # type: ignore
from port_ocean.context.ocean import PortOceanContext, initialize_port_ocean_context
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "iam-policy-binding"
EXTRA_PROJECT_FIELD = "__project"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    """Rate-limiter defaults read the integration config at import time."""
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
    from gcp_core.search.resource_searches import expand_iam_policy_bindings

    scope = _project_scope()
    policies = [
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
                    {"members": ["user:ignored@example.com"]},
                    {"role": "roles/editor", "members": []},
                ]
            },
        }
    ]

    entities = expand_iam_policy_bindings(policies, scope, EXTRA_PROJECT_FIELD)

    assert entities == [
        {
            "resource": "//cloudresourcemanager.googleapis.com/projects/my-project",
            "asset_type": "cloudresourcemanager.googleapis.com/Project",
            "project": "projects/123456789",
            "folders": ["folders/111"],
            "organization": "organizations/222",
            "role": "roles/viewer",
            "member": "serviceAccount:app@my-project.iam.gserviceaccount.com",
            "member_type": "serviceAccount",
            "member_id": "app@my-project.iam.gserviceaccount.com",
            "condition": None,
            EXTRA_PROJECT_FIELD: scope,
        },
        {
            "resource": "//cloudresourcemanager.googleapis.com/projects/my-project",
            "asset_type": "cloudresourcemanager.googleapis.com/Project",
            "project": "projects/123456789",
            "folders": ["folders/111"],
            "organization": "organizations/222",
            "role": "roles/viewer",
            "member": "allUsers",
            "member_type": "allUsers",
            "member_id": "",
            "condition": None,
            EXTRA_PROJECT_FIELD: scope,
        },
        {
            "resource": "//cloudresourcemanager.googleapis.com/projects/my-project",
            "asset_type": "cloudresourcemanager.googleapis.com/Project",
            "project": "projects/123456789",
            "folders": ["folders/111"],
            "organization": "organizations/222",
            "role": "roles/owner",
            "member": "user:alex@example.com",
            "member_type": "user",
            "member_id": "alex@example.com",
            "condition": {
                "expression": "request.time < timestamp('2026-01-01T00:00:00Z')",
                "title": "until",
                "description": "",
                "location": "",
            },
            EXTRA_PROJECT_FIELD: scope,
        },
    ]


def test_expand_reads_protobuf_policy_shape() -> None:
    from gcp_core.search.resource_searches import expand_iam_policy_bindings

    result = IamPolicySearchResult(
        resource="//iam.googleapis.com/projects/my-project/serviceAccounts/123",
        asset_type="iam.googleapis.com/ServiceAccount",
        project="projects/123",
        policy=Policy(
            bindings=[
                Binding(
                    role="roles/iam.serviceAccountUser",
                    members=["deleted:user:alex@example.com?uid=1"],
                    condition=Expr(expression="true", title="always"),
                )
            ]
        ),
    )
    policy = proto.Message.to_dict(result, preserving_proto_field_name=True)
    scope = {"name": "folders/7"}

    entities = expand_iam_policy_bindings(policy and [policy], scope, "__folder")

    assert len(entities) == 1
    assert entities[0]["asset_type"] == "iam.googleapis.com/ServiceAccount"
    assert entities[0]["member_type"] == "deleted"
    assert entities[0]["member_id"] == "user:alex@example.com?uid=1"
    assert entities[0]["condition"]["expression"] == "true"
    assert entities[0]["__folder"] == scope
    assert EXTRA_PROJECT_FIELD not in entities[0]


def test_partition_keeps_folder_and_organization_on_their_own_scopes() -> None:
    from gcp_core.search.resource_searches import partition_iam_policy_asset_types
    from gcp_core.utils import AssetTypesWithSpecialHandling

    project_types, include_folders, include_organizations = (
        partition_iam_policy_asset_types(
            [
                "iam.googleapis.com/ServiceAccount",
                AssetTypesWithSpecialHandling.FOLDER,
                "cloudresourcemanager.googleapis.com/Project",
                AssetTypesWithSpecialHandling.ORGANIZATION,
            ]
        )
    )

    assert project_types == [
        "iam.googleapis.com/ServiceAccount",
        "cloudresourcemanager.googleapis.com/Project",
    ]
    assert include_folders is True
    assert include_organizations is True


@pytest.mark.asyncio
async def test_search_sends_scope_asset_types_query_and_max_page_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import resource_searches

    captured: list[dict[str, Any]] = []

    class FakeAssetClient:
        async def search_all_iam_policies(
            self, request: dict[str, Any], timeout: float | None = None
        ) -> Any:
            del timeout
            captured.append(dict(request))
            response = MagicMock()
            response.results = [
                {
                    "resource": "//compute.googleapis.com/projects/my-project/zones/z/instances/vm",
                    "asset_type": "compute.googleapis.com/Instance",
                    "project": "projects/123",
                    "policy": {
                        "bindings": [
                            {
                                "role": "roles/compute.viewer",
                                "members": [f"serviceAccount:sa-{index}@example.com"],
                            }
                            for index in range(101)
                        ]
                    },
                }
            ]
            response.next_page_token = ""
            return response

    monkeypatch.setattr(
        resource_searches, "get_asset_client", lambda: FakeAssetClient()
    )
    monkeypatch.setattr(
        resource_searches, "parse_protobuf_messages", lambda results: results
    )

    scope = _project_scope()
    batches: list[list[dict[str, Any]]] = []
    async for batch in resource_searches.search_all_iam_policies_in_scope(
        scope,
        BoundedSemaphore(1),
        ["compute.googleapis.com/Instance"],
        policy_query="memberTypes:serviceAccount",
    ):
        batches.append(batch)

    assert captured == [
        {
            "scope": "projects/my-project",
            "asset_types": ["compute.googleapis.com/Instance"],
            "query": "memberTypes:serviceAccount",
            "page_size": 500,
        }
    ]
    assert [len(batch) for batch in batches] == [100, 1]
    assert batches[0][0]["role"] == "roles/compute.viewer"
    assert batches[0][0][EXTRA_PROJECT_FIELD] == scope


@pytest.mark.asyncio
async def test_search_omits_blank_policy_query(
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

    async for _ in resource_searches.search_all_iam_policies_in_scope(
        _project_scope(),
        BoundedSemaphore(1),
        ["iam.googleapis.com/ServiceAccount"],
        policy_query=None,
    ):
        pass

    assert captured[0]["method"] == "search_all_iam_policies"
    assert "query" not in captured[0]["request"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [PermissionDenied("missing permission"), NotFound("scope missing")],
)
async def test_search_swallows_permission_and_not_found(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    from gcp_core.search import resource_searches

    async def fake_paginated_query(
        *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise error
        yield []

    monkeypatch.setattr(resource_searches, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(resource_searches, "get_asset_client", lambda: MagicMock())

    batches = [
        batch
        async for batch in resource_searches.search_all_iam_policies_in_scope(
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
    from gcp_core.search import resource_searches

    async def fake_paginated_query(
        *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise ValueError("boom")
        yield []

    monkeypatch.setattr(resource_searches, "paginated_query", fake_paginated_query)
    monkeypatch.setattr(resource_searches, "get_asset_client", lambda: MagicMock())

    with pytest.raises(ValueError, match="boom"):
        async for _ in resource_searches.search_all_iam_policies_in_scope(
            _project_scope(),
            BoundedSemaphore(1),
            ["cloudresourcemanager.googleapis.com/Project"],
        ):
            pass


@pytest.mark.asyncio
async def test_project_asset_types_are_not_searched_at_org_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import resource_searches

    searched: list[list[str]] = []

    async def fake_iterate(
        fn: Any, *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del fn, args
        searched.append(list(kwargs["asset_types"]))
        yield [{"resource": "projects/my-project"}]

    async def unexpected_scope_search() -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise AssertionError("folder and organization scopes must not be searched")
        yield []

    monkeypatch.setattr(
        "gcp_core.search.iterators.iterate_per_available_project", fake_iterate
    )
    monkeypatch.setattr(
        resource_searches, "search_all_folders", unexpected_scope_search
    )
    monkeypatch.setattr(
        resource_searches, "search_all_organizations", unexpected_scope_search
    )

    batches = [
        batch
        async for batch in resource_searches.search_explicit_iam_policy_bindings(
            ["iam.googleapis.com/ServiceAccount"],
            "memberTypes:serviceAccount",
            rate_limiter=MagicMock(),
            semaphore=BoundedSemaphore(1),
        )
    ]

    assert searched == [["iam.googleapis.com/ServiceAccount"]]
    assert batches == [[{"resource": "projects/my-project"}]]


@pytest.mark.asyncio
async def test_folder_and_organization_types_use_their_own_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gcp_core.search import resource_searches
    from gcp_core.utils import AssetTypesWithSpecialHandling

    seen: list[tuple[str, list[str], str]] = []

    async def fake_folders() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"name": "folders/7"}]

    async def fake_organizations() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"name": "organizations/9"}]

    async def fake_search(
        scope: dict[str, Any],
        semaphore: BoundedSemaphore,
        asset_types: list[str],
        policy_query: str | None = None,
        rate_limiter: Any = None,
        scope_field: str = EXTRA_PROJECT_FIELD,
        asset_type: str | None = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del semaphore, policy_query, rate_limiter, asset_type
        seen.append((scope["name"], list(asset_types), scope_field))
        yield [{"scope": scope["name"]}]

    async def unexpected_project_search(
        *args: Any, **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        del args, kwargs
        raise AssertionError("project iteration must not run")
        yield []

    monkeypatch.setattr(resource_searches, "search_all_folders", fake_folders)
    monkeypatch.setattr(
        resource_searches, "search_all_organizations", fake_organizations
    )
    monkeypatch.setattr(
        resource_searches, "search_all_iam_policies_in_scope", fake_search
    )
    monkeypatch.setattr(
        "gcp_core.search.iterators.iterate_per_available_project",
        unexpected_project_search,
    )

    batches = [
        batch
        async for batch in resource_searches.search_explicit_iam_policy_bindings(
            [
                AssetTypesWithSpecialHandling.FOLDER,
                AssetTypesWithSpecialHandling.ORGANIZATION,
            ],
            None,
            rate_limiter=MagicMock(),
            semaphore=BoundedSemaphore(1),
        )
    ]

    assert seen == [
        ("folders/7", [AssetTypesWithSpecialHandling.FOLDER], "__folder"),
        (
            "organizations/9",
            [AssetTypesWithSpecialHandling.ORGANIZATION],
            "__organization",
        ),
    ]
    assert batches == [[{"scope": "folders/7"}], [{"scope": "organizations/9"}]]


def test_example_raw_matches_expanded_binding_and_mapping() -> None:
    import jq  # type: ignore[import-not-found]

    from gcp_core.search.resource_searches import expand_iam_policy_bindings

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
            "policy": {
                "bindings": [
                    {
                        "role": raw["role"],
                        "members": [raw["member"]],
                    }
                ]
            },
        }
    ]

    assert expand_iam_policy_bindings(policies, scope, EXTRA_PROJECT_FIELD) == [raw]

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
            "memberType": jq.compile(".member_type").input_value(raw).first(),
            "resource": jq.compile(".resource").input_value(raw).first(),
            "assetType": jq.compile(".asset_type").input_value(raw).first(),
            "condition": jq.compile('.condition.expression // ""')
            .input_value(raw)
            .first(),
        },
        "relations": {
            "project": jq.compile(".__project.name").input_value(raw).first(),
        },
    }
    assert mapped == expected
