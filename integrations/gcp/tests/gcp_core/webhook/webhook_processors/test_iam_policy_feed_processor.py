import base64
import json
from contextlib import contextmanager
from typing import Any, AsyncIterator, Generator, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import port_ocean.context.ocean as ocean_context_module
import pytest
from google.cloud.asset_v1 import IamPolicySearchResult
from google.iam.v1 import policy_pb2  # type: ignore[import-untyped]
from google.protobuf import json_format  # type: ignore[import-untyped]
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
)
from port_ocean.context.event import EventType, event_context
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

ASSET_TYPE = "iam.googleapis.com/ServiceAccount"
ASSET_NAME = "//iam.googleapis.com/projects/test-project/serviceAccounts/sa@test-project.iam.gserviceaccount.com"
ASSET_PROJECT = "projects/123456789"
ASSET_ORGANIZATION = "organizations/123"
IAM_POLICY_KIND = "iamPolicy"

CONDITION = {
    "expression": "request.time < timestamp('2030-01-01T00:00:00Z')",
    "title": "expires-2030",
}
PRIOR_POLICY: dict[str, Any] = {
    "bindings": [
        {
            "role": "roles/viewer",
            "members": ["user:kept@example.com", "user:revoked@example.com"],
            "condition": CONDITION,
        }
    ]
}
NEW_POLICY: dict[str, Any] = {
    "bindings": [
        {
            "role": "roles/viewer",
            "members": ["user:kept@example.com"],
            "condition": CONDITION,
        }
    ]
}


def _encode_asset_data(asset_data: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(asset_data).encode()).decode()


def _pubsub_payload(asset_data: dict[str, Any]) -> EventPayload:
    return {"message": {"data": _encode_asset_data(asset_data)}}


def _resync_raw_item(policy: policy_pb2.Policy) -> dict[str, Any]:
    """Build the raw item the way search_all_iam_policies_per_project does, from proto objects."""
    from gcp_core.overrides import ProtoConfig
    from gcp_core.utils import parse_protobuf_message

    return parse_protobuf_message(
        IamPolicySearchResult(
            resource=ASSET_NAME,
            asset_type=ASSET_TYPE,
            project=ASSET_PROJECT,
            # searchAllIamPolicies fills these from the asset's ancestry, so the live path must too.
            organization=ASSET_ORGANIZATION,
            policy=policy,
        ),
        ProtoConfig(preserving_proto_field_name=False),
    )


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    mock_app: MagicMock = MagicMock()
    mock_app.config.integration.config = {
        "search_all_resources_per_minute_quota": 100,
        "encoded_adc_configuration": None,
    }
    mock_app.integration_router = MagicMock()
    mock_app.port_client = MagicMock()
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)
    yield
    ocean_context_module._port_ocean = PortOceanContext(None)


@pytest.fixture(autouse=True)
async def event_ctx(mock_ocean_context: None) -> AsyncIterator[None]:
    """handle_event runs inside the webhook manager's event context, and parse_protobuf_message
    reads the selector off it."""
    async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
        yield


@pytest.fixture
def asset_payload() -> dict[str, Any]:
    return {
        "asset": {
            "assetType": ASSET_TYPE,
            "name": ASSET_NAME,
            "ancestors": [ASSET_PROJECT, "organizations/123"],
            "iamPolicy": NEW_POLICY,
        },
        "priorAsset": {
            "assetType": ASSET_TYPE,
            "name": ASSET_NAME,
            "iamPolicy": PRIOR_POLICY,
        },
        "priorAssetState": "PRESENT",
        "deleted": False,
    }


@pytest.fixture
def processor(mock_ocean_context: None, asset_payload: dict[str, Any]) -> Any:
    from gcp_core.webhook.webhook_processors.iam_policy_feed_processor import (
        IamPolicyFeedProcessor,
    )

    return IamPolicyFeedProcessor(
        event=WebhookEvent(
            trace_id="test-trace-id",
            headers={},
            payload=_pubsub_payload(asset_payload),
        )
    )


@pytest.fixture
def resource_config(mock_ocean_context: None) -> MagicMock:
    from gcp_core.overrides import GCPIamPolicySelector

    config = MagicMock()
    config.kind = IAM_POLICY_KIND
    config.selector = GCPIamPolicySelector(query="true", assetTypes=[ASSET_TYPE])
    return config


@contextmanager
def _patch_asset_search(assets: list[dict[str, Any]] | None = None) -> Iterator[None]:
    """`search_asset_names_in_project` hits the Cloud Asset API. The default says the feed's own
    name is already the one searchAllIamPolicies returns, which is true for buckets and topics.
    """
    module = "gcp_core.webhook.webhook_processors.iam_policy_feed_processor"
    if assets is None:
        assets = [{"name": ASSET_NAME, "aliases": []}]
    with patch(
        f"{module}.search_asset_names_in_project", new=AsyncMock(return_value=assets)
    ):
        yield


class TestGetMatchingKinds:
    async def test_always_returns_the_iam_policy_kind(self, processor: Any) -> None:
        # The manager drops the event when the kind is absent from the mapping, and pairs the
        # kind with every iamPolicy resource in it, so neither check belongs here.
        assert await processor.get_matching_kinds(processor.event) == [IAM_POLICY_KIND]


class TestHandleEvent:
    async def test_binding_edit_returns_new_as_updated_and_prior_as_deleted(
        self,
        processor: Any,
        asset_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        with _patch_asset_search():
            result = await processor.handle_event(
                _pubsub_payload(asset_payload), resource_config
            )

        assert [r["policy"] for r in result.updated_raw_results] == [
            _resync_raw_item(json_format.ParseDict(NEW_POLICY, policy_pb2.Policy()))[
                "policy"
            ]
        ]
        assert [r["policy"] for r in result.deleted_raw_results] == [
            _resync_raw_item(json_format.ParseDict(PRIOR_POLICY, policy_pb2.Policy()))[
                "policy"
            ]
        ]

    async def test_deleted_asset_returns_prior_only(
        self, processor: Any, resource_config: MagicMock
    ) -> None:
        deleted_payload = {
            "asset": {
                "assetType": ASSET_TYPE,
                "name": ASSET_NAME,
                "ancestors": [ASSET_PROJECT],
            },
            "priorAsset": {"iamPolicy": PRIOR_POLICY},
            "deleted": True,
        }
        with _patch_asset_search():
            result = await processor.handle_event(
                _pubsub_payload(deleted_payload), resource_config
            )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1

    async def test_first_known_state_returns_updated_only(
        self, processor: Any, asset_payload: dict[str, Any], resource_config: MagicMock
    ) -> None:
        payload = {k: v for k, v in asset_payload.items() if k != "priorAsset"}
        payload["priorAssetState"] = "DOES_NOT_EXIST"
        with _patch_asset_search():
            result = await processor.handle_event(
                _pubsub_payload(payload), resource_config
            )

        assert len(result.updated_raw_results) == 1
        assert result.deleted_raw_results == []

    async def test_cleared_policy_returns_an_empty_policy_and_deletes_the_prior(
        self, processor: Any, asset_payload: dict[str, Any], resource_config: MagicMock
    ) -> None:
        payload = json.loads(json.dumps(asset_payload))
        del payload["asset"]["iamPolicy"]
        with _patch_asset_search():
            result = await processor.handle_event(
                _pubsub_payload(payload), resource_config
            )

        assert result.updated_raw_results[0]["policy"]["bindings"] == []
        assert len(result.deleted_raw_results) == 1

    @pytest.mark.parametrize(
        "ancestors",
        [
            pytest.param(["organizations/123"], id="no_project_ancestor"),
            pytest.param([], id="empty_ancestors"),
            pytest.param(None, id="ancestors_absent"),
        ],
    )
    async def test_returns_empty_results_without_a_project_ancestor(
        self,
        processor: Any,
        asset_payload: dict[str, Any],
        resource_config: MagicMock,
        ancestors: list[str] | None,
    ) -> None:
        payload = json.loads(json.dumps(asset_payload))
        if ancestors is None:
            del payload["asset"]["ancestors"]
        else:
            payload["asset"]["ancestors"] = ancestors

        with _patch_asset_search():
            result = await processor.handle_event(
                _pubsub_payload(payload), resource_config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_skips_an_asset_type_outside_this_resources_asset_types(
        self, processor: Any, asset_payload: dict[str, Any]
    ) -> None:
        from gcp_core.overrides import GCPIamPolicySelector

        config = MagicMock()
        config.selector = GCPIamPolicySelector(
            query="true", assetTypes=["storage.googleapis.com/Bucket"]
        )
        with _patch_asset_search():
            result = await processor.handle_event(
                _pubsub_payload(asset_payload), config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_skips_a_resource_that_filters_its_policies_server_side(
        self, processor: Any, asset_payload: dict[str, Any]
    ) -> None:
        from gcp_core.overrides import GCPIamPolicySelector

        config = MagicMock()
        config.selector = GCPIamPolicySelector(
            query="true",
            assetTypes=[ASSET_TYPE],
            policyQuery="memberTypes:serviceAccount",
        )
        with _patch_asset_search():
            result = await processor.handle_event(
                _pubsub_payload(asset_payload), config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_conditional_binding_matches_the_resync_byte_for_byte(
        self,
        processor: Any,
        asset_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """The identifier hashes `.item.condition | tojson`, and json_format drops the proto
        defaults that proto.Message.to_dict keeps. Passing the feed's policy through unrebuilt
        yields a second entity for a grant the resync already owns."""
        resync_policy = policy_pb2.Policy()
        binding = resync_policy.bindings.add()
        binding.role = "roles/viewer"
        binding.members.append("user:kept@example.com")
        binding.condition.expression = CONDITION["expression"]
        binding.condition.title = CONDITION["title"]

        with _patch_asset_search():
            result = await processor.handle_event(
                _pubsub_payload(asset_payload), resource_config
            )

        assert result.updated_raw_results == [_resync_raw_item(resync_policy)]
        assert (
            result.updated_raw_results[0]["policy"]["bindings"][0]["condition"]
            != NEW_POLICY["bindings"][0]["condition"]
        )


# Captured from a real content-type=iam-policy feed on 2026-11-18 (sendbox-go), by revoking
# roles/iam.serviceAccountViewer. Note `asset.name` carries the service account's numeric uniqueId
# while searchAllIamPolicies returns its email, and that `deleted` is absent rather than false.
REAL_FEED_EVENT: dict[str, Any] = {
    "asset": {
        "ancestors": [
            "projects/385573848890",
            "folders/682955879488",
            "organizations/297901551190",
        ],
        "assetType": "iam.googleapis.com/ServiceAccount",
        "iamPolicy": {
            "bindings": [
                {
                    "members": [
                        "serviceAccount:terraform-sa@sendbox-go.iam.gserviceaccount.com"
                    ],
                    "role": "roles/iam.serviceAccountUser",
                }
            ]
        },
        "name": "//iam.googleapis.com/projects/sendbox-go/serviceAccounts/102224987541154455550",
        "updateTime": "2026-11-18T11:50:57.530656Z",
    },
    "priorAsset": {
        "ancestors": ["projects/385573848890"],
        "assetType": "iam.googleapis.com/ServiceAccount",
        "iamPolicy": {
            "bindings": [
                {
                    "members": [
                        "serviceAccount:terraform-sa@sendbox-go.iam.gserviceaccount.com"
                    ],
                    "role": "roles/iam.serviceAccountUser",
                },
                {
                    "members": [
                        "serviceAccount:ocean-test@sendbox-go.iam.gserviceaccount.com"
                    ],
                    "role": "roles/iam.serviceAccountViewer",
                },
            ]
        },
        "name": "//iam.googleapis.com/projects/sendbox-go/serviceAccounts/102224987541154455550",
    },
    "priorAssetState": "PRESENT",
    "window": {"startTime": "2026-11-18T11:50:57.530656Z"},
}
CANONICAL = "//iam.googleapis.com/projects/sendbox-go/serviceAccounts/terraform-sa@sendbox-go.iam.gserviceaccount.com"
REAL_ALIASES = [
    {
        "name": CANONICAL,
        "aliases": [
            "102224987541154455550",
            "terraform-sa@sendbox-go.iam.gserviceaccount.com",
        ],
    },
    {
        "name": "//iam.googleapis.com/projects/sendbox-go/serviceAccounts/other@sendbox-go.iam.gserviceaccount.com",
        "aliases": ["999"],
    },
]


class TestRealFeedEvent:
    @pytest.fixture
    def sa_config(self, mock_ocean_context: None) -> MagicMock:
        from gcp_core.overrides import GCPIamPolicySelector

        config = MagicMock()
        config.selector = GCPIamPolicySelector(
            query="true", assetTypes=["iam.googleapis.com/ServiceAccount"]
        )
        return config

    async def test_numeric_feed_name_resolves_to_the_resync_name(
        self, processor: Any, sa_config: MagicMock
    ) -> None:
        """The feed names a service account by uniqueId and searchAllIamPolicies by email. Using
        the feed's name verbatim mints a second entity for a grant the resync already owns.
        """
        with _patch_asset_search(REAL_ALIASES):
            result = await processor.handle_event(
                _pubsub_payload(REAL_FEED_EVENT), sa_config
            )

        assert [r["resource"] for r in result.updated_raw_results] == [CANONICAL]
        assert [r["resource"] for r in result.deleted_raw_results] == [CANONICAL]
        assert all(
            "102224987541154455550" not in r["resource"]
            for r in result.updated_raw_results + result.deleted_raw_results
        )

    async def test_revoked_grant_is_the_only_difference(
        self, processor: Any, sa_config: MagicMock
    ) -> None:
        with _patch_asset_search(REAL_ALIASES):
            result = await processor.handle_event(
                _pubsub_payload(REAL_FEED_EVENT), sa_config
            )

        def grants(items: list[dict[str, Any]]) -> set[tuple[str, str]]:
            return {
                (binding["role"], member)
                for item in items
                for binding in item["policy"]["bindings"]
                for member in binding["members"]
            }

        assert grants(result.deleted_raw_results) - grants(
            result.updated_raw_results
        ) == {
            (
                "roles/iam.serviceAccountViewer",
                "serviceAccount:ocean-test@sendbox-go.iam.gserviceaccount.com",
            )
        }

    async def test_project_is_read_from_ancestors_not_the_name(
        self, processor: Any, sa_config: MagicMock
    ) -> None:
        with _patch_asset_search(REAL_ALIASES):
            result = await processor.handle_event(
                _pubsub_payload(REAL_FEED_EVENT), sa_config
            )

        assert result.updated_raw_results[0]["project"] == "projects/385573848890"

    async def test_ancestors_fill_folders_and_organization(
        self, processor: Any, sa_config: MagicMock
    ) -> None:
        """searchAllIamPolicies returns organization and folders alongside project. Nothing ships a
        default iamPolicy mapping, so every mapping is hand-written and may read either.
        """
        with _patch_asset_search(REAL_ALIASES):
            result = await processor.handle_event(
                _pubsub_payload(REAL_FEED_EVENT), sa_config
            )

        item = result.updated_raw_results[0]
        assert item["project"] == "projects/385573848890"
        assert item["folders"] == ["folders/682955879488"]
        assert item["organization"] == "organizations/297901551190"

    async def test_unresolvable_asset_is_skipped_rather_than_duplicated(
        self, processor: Any, sa_config: MagicMock
    ) -> None:
        """Declining loses the change until the next resync; guessing creates an entity no resync
        ever reconciles away."""
        with _patch_asset_search([{"name": "//x/y", "aliases": ["nope"]}]):
            result = await processor.handle_event(
                _pubsub_payload(REAL_FEED_EVENT), sa_config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []


class TestAliasMatching:
    """additionalAttributes is absent for types that do not alias (buckets, topics, repositories)
    and carries only identity values where it is present. Both verified against sendbox-go.
    """

    async def test_bucket_with_no_aliases_resolves_by_exact_name(
        self, processor: Any
    ) -> None:
        from gcp_core.overrides import GCPIamPolicySelector

        bucket = "//storage.googleapis.com/sendbox-go-terraform"
        payload = {
            "asset": {
                "assetType": "storage.googleapis.com/Bucket",
                "name": bucket,
                "ancestors": [ASSET_PROJECT],
                "iamPolicy": NEW_POLICY,
            },
            "deleted": False,
        }
        config = MagicMock()
        config.selector = GCPIamPolicySelector(
            query="true", assetTypes=["storage.googleapis.com/Bucket"]
        )
        with _patch_asset_search([{"name": bucket, "aliases": []}]):
            result = await processor.handle_event(_pubsub_payload(payload), config)

        assert [r["resource"] for r in result.updated_raw_results] == [bucket]

    async def test_an_alias_must_replace_the_whole_final_segment(
        self, processor: Any, asset_payload: dict[str, Any], resource_config: MagicMock
    ) -> None:
        """A free-text attribute that merely ends the feed's name must not win the match."""
        decoy = {
            "name": "//iam.googleapis.com/projects/other-project/serviceAccounts/decoy@x.com",
            "aliases": [ASSET_NAME.rsplit("/", 1)[-1]],
        }
        with _patch_asset_search([decoy]):
            result = await processor.handle_event(
                _pubsub_payload(asset_payload), resource_config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []


PROJECT_TYPE = "cloudresourcemanager.googleapis.com/Project"
PROJECT_CANONICAL = "//cloudresourcemanager.googleapis.com/projects/sendbox-go"
PROJECT_FEED_NAME = "//cloudresourcemanager.googleapis.com/projects/385573848890"


class TestProjectAssetResolution:
    """A feed names a project by its number; searchAllResources names it by its id and does not
    index the number, so the narrowing query finds nothing and the unfiltered listing is the only
    way through. Verified against sendbox-go."""

    @pytest.fixture
    def project_payload(self) -> dict[str, Any]:
        return {
            "asset": {
                "assetType": PROJECT_TYPE,
                "name": PROJECT_FEED_NAME,
                "ancestors": [ASSET_PROJECT],
                "iamPolicy": NEW_POLICY,
            },
            "deleted": False,
        }

    @pytest.fixture
    def project_config(self, mock_ocean_context: None) -> MagicMock:
        from gcp_core.overrides import GCPIamPolicySelector

        config = MagicMock()
        config.selector = GCPIamPolicySelector(query="true", assetTypes=[PROJECT_TYPE])
        return config

    async def test_falls_back_to_the_listing_when_the_query_finds_nothing(
        self, processor: Any, project_payload: dict[str, Any], project_config: MagicMock
    ) -> None:
        module = "gcp_core.webhook.webhook_processors.iam_policy_feed_processor"
        listed = [
            {"name": PROJECT_CANONICAL, "aliases": ["sendbox-go", "385573848890"]}
        ]
        search = AsyncMock(return_value=[])
        listing = AsyncMock(return_value=listed)
        with (
            patch(f"{module}.search_asset_names_in_project", new=search),
            patch(f"{module}.list_asset_names_in_project", new=listing),
        ):
            result = await processor.handle_event(
                _pubsub_payload(project_payload), project_config
            )

        assert [r["resource"] for r in result.updated_raw_results] == [
            PROJECT_CANONICAL
        ]
        # The narrowed search first, then the unfiltered listing.
        assert search.await_args_list[0].args[2] == "385573848890"
        assert listing.await_count == 1

    async def test_a_non_project_type_does_not_fall_back_to_listing(
        self, processor: Any, asset_payload: dict[str, Any], resource_config: MagicMock
    ) -> None:
        """Listing a type to find one asset is affordable only because a project scope holds one
        project. One sandbox project holds 4,751 container images, which would be 48 paged calls
        inside a single webhook event."""
        module = "gcp_core.webhook.webhook_processors.iam_policy_feed_processor"
        search = AsyncMock(return_value=[])
        listing = AsyncMock(return_value=[{"name": ASSET_NAME, "aliases": []}])
        with (
            patch(f"{module}.search_asset_names_in_project", new=search),
            patch(f"{module}.list_asset_names_in_project", new=listing),
        ):
            result = await processor.handle_event(
                _pubsub_payload(asset_payload), resource_config
            )

        assert listing.await_count == 0
        assert search.await_count == 1
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []


class TestSearchRequest:
    async def test_the_search_term_is_quoted(self) -> None:
        """A resource name's final segment may hold a `:` (a container image digest), which is
        query syntax and 400s the request unquoted. 4,761 of 4,937 assets in sendbox-go do.
        """
        from gcp_core.search import resource_searches

        captured: dict[str, Any] = {}

        async def fake_paginated_query(
            client: Any, method: str, request: dict[str, Any], parse: Any, limiter: Any
        ) -> Any:
            captured.update(request)
            return
            yield  # pragma: no cover - makes this an async generator

        controllers = MagicMock()
        controllers.limiter = AsyncMock(return_value=MagicMock())
        controllers.semaphore = AsyncMock(return_value=AsyncMock())
        with (
            patch.object(resource_searches, "paginated_query", fake_paginated_query),
            patch.object(resource_searches, "get_asset_client", MagicMock()),
            patch.object(
                resource_searches,
                "get_service_account_project_id",
                lambda: "sendbox-go",
            ),
            patch.object(
                resource_searches, "search_all_resources_qpm_per_project", controllers
            ),
        ):
            await resource_searches.search_asset_names_in_project(
                "projects/x",
                "containerregistry.googleapis.com/Image",
                "headless-shipping@sha256:5d26e",
            )

        assert captured["query"] == '"headless-shipping@sha256:5d26e"'
        assert "project" in captured["read_mask"]


class TestAliasAmbiguity:
    """Every asset reports the same project number. Treating it as a general alias made each asset
    of a type answer to it, and the first in the list won: 35 of 148 real name forms in sendbox-go
    resolved to the wrong asset."""

    def test_the_project_number_is_an_alias_only_for_the_project(self) -> None:
        from gcp_core.search.resource_searches import _asset_aliases

        project = MagicMock()
        project.name = "//cloudresourcemanager.googleapis.com/projects/sendbox-go"
        project.project = "projects/385573848890"
        project.additional_attributes = {"projectId": "sendbox-go"}

        bucket = MagicMock()
        bucket.name = "//storage.googleapis.com/sendbox-go-terraform"
        bucket.project = "projects/385573848890"
        bucket.additional_attributes = None

        assert "385573848890" in _asset_aliases(project)
        assert _asset_aliases(bucket) == []

    def test_an_alias_shared_by_several_assets_resolves_to_none(self) -> None:
        from gcp_core.feed_event import canonical_resource_name

        shared = [
            {
                "name": "//iam.googleapis.com/projects/p/serviceAccounts/a@x.com",
                "aliases": ["999"],
            },
            {
                "name": "//iam.googleapis.com/projects/p/serviceAccounts/b@x.com",
                "aliases": ["999"],
            },
        ]
        feed = "//iam.googleapis.com/projects/p/serviceAccounts/999"
        assert canonical_resource_name(feed, shared) is None

    def test_an_alias_held_by_exactly_one_asset_still_resolves(self) -> None:
        from gcp_core.feed_event import canonical_resource_name

        assets = [
            {
                "name": "//iam.googleapis.com/projects/p/serviceAccounts/a@x.com",
                "aliases": ["999"],
            },
            {
                "name": "//iam.googleapis.com/projects/p/serviceAccounts/b@x.com",
                "aliases": ["888"],
            },
        ]
        feed = "//iam.googleapis.com/projects/p/serviceAccounts/999"
        assert (
            canonical_resource_name(feed, assets)
            == "//iam.googleapis.com/projects/p/serviceAccounts/a@x.com"
        )
