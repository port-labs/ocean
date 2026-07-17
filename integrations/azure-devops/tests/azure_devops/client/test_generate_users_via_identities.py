"""Tests for generate_users_via_identities and its private helper methods.

Covers:
- _is_builtin_identity: built-in filtering logic
- _extract_project_entitlements: scope-ID → projectRef mapping and dedup
- _build_user_shape_from_graph_user: output envelope shape
- _fetch_identities_for_descriptors: batching at MAX_IDENTITIES_PER_REQUEST
- _enumerate_graph_users: pagination delegation
- generate_users_via_identities: full flow including built-in filtering, project
  membership resolution, and toggle routing
"""
from typing import Any, AsyncGenerator, Dict, Generator, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.event import EventContext
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from azure_devops.client.auth import PatAuthProvider
from azure_devops.client.azure_devops_client import (
    MAX_IDENTITIES_PER_REQUEST,
    AzureDevopsClient,
)

MOCK_ORG_URL = "https://dev.azure.com/testorg"
MOCK_PERSONAL_ACCESS_TOKEN = "test-pat-token"
MOCK_AUTH_PROVIDER = PatAuthProvider(MOCK_PERSONAL_ACCESS_TOKEN)
MOCK_AUTH_USERNAME = "port"


# ── test-session fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize a minimal PortOcean context so AzureDevopsClient can be instantiated."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": MOCK_PERSONAL_ACCESS_TOKEN,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._deadline = 999999999.0
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event


# ── fixtures ──────────────────────────────────────────────────────────────────

MOCK_GRAPH_USER = {
    "subjectKind": "user",
    "descriptor": "aad.abc123",
    "displayName": "Alice Example",
    "mailAddress": "alice@example.com",
    "principalName": "alice@example.com",
    "url": "https://vssps.dev.azure.com/myorg/_apis/Graph/Users/aad.abc123",
    "origin": "aad",
    "originId": "aaaa-bbbb-cccc-dddd",
    "domain": "some-tenant-guid",
    "_links": {},
}

MOCK_GRAPH_USER_2 = {
    "subjectKind": "user",
    "descriptor": "aad.xyz789",
    "displayName": "Bob Example",
    "mailAddress": "bob@example.com",
    "principalName": "bob@example.com",
    "url": "https://vssps.dev.azure.com/myorg/_apis/Graph/Users/aad.xyz789",
    "origin": "aad",
    "originId": "1111-2222-3333-4444",
    "domain": "some-tenant-guid",
    "_links": {},
}

MOCK_BUILTIN_GRAPH_USER = {
    "subjectKind": "user",
    "descriptor": "scp.scope123",
    "displayName": "Build Service",
    "mailAddress": "",
    "principalName": "",
    "url": "https://vssps.dev.azure.com/myorg/_apis/Graph/Users/scp.scope123",
    "origin": "vsts",
    "originId": "builtin-guid",
    "domain": "",
    "_links": {},
}

# Identity returned by vssps/_apis/identities with queryMembership=expandedUp.
MOCK_IDENTITY_EXPANDED = {
    "subjectDescriptor": "aad.abc123",
    "providerDisplayName": "Alice Example",
    "id": "aaaa-bbbb-cccc-dddd",
    "memberOf": [
        {"subjectDescriptor": "vssgp.group1"},
        {"subjectDescriptor": "vssgp.group2"},
    ],
}

MOCK_IDENTITY_EXPANDED_2 = {
    "subjectDescriptor": "aad.xyz789",
    "providerDisplayName": "Bob Example",
    "id": "1111-2222-3333-4444",
    "memberOf": [
        {"subjectDescriptor": "vssgp.group1"},
    ],
}

MOCK_BUILTIN_IDENTITY = {
    "subjectDescriptor": "scp.scope123",
    "providerDisplayName": "[TEAM FOUNDATION]\\Build Service",
    "id": "builtin-guid",
    "memberOf": [],
}

# Group identities (returned by the batch-resolve call, no expandedUp).
MOCK_GROUP_IDENTITY_PROJECT_A = {
    "subjectDescriptor": "vssgp.group1",
    "providerDisplayName": "Project A\\Contributors",
    "id": "grp1-guid",
    "scopeId": "proj-a-guid",  # matches a project GUID
}

MOCK_GROUP_IDENTITY_PROJECT_B = {
    "subjectDescriptor": "vssgp.group2",
    "providerDisplayName": "Project B\\Readers",
    "id": "grp2-guid",
    "scopeId": "proj-b-guid",
}

MOCK_GROUP_IDENTITY_NO_SCOPE = {
    "subjectDescriptor": "vssgp.group3",
    "providerDisplayName": "Collection-level group",
    "id": "grp3-guid",
    "scopeId": "",  # org-scoped, no project match
}

MOCK_PROJECTS = [
    {"id": "proj-a-guid", "name": "Project A"},
    {"id": "proj-b-guid", "name": "Project B"},
]


# ── _is_builtin_identity ──────────────────────────────────────────────────────


def test_is_builtin_identity_filters_team_foundation() -> None:
    """Identities whose providerDisplayName starts with [TEAM FOUNDATION] are built-ins."""
    assert AzureDevopsClient._is_builtin_identity(MOCK_BUILTIN_IDENTITY) is True


def test_is_builtin_identity_filters_scp_descriptor() -> None:
    """Identities with a subjectDescriptor starting with 'scp.' are scope entries."""
    identity = {"subjectDescriptor": "scp.abc", "providerDisplayName": "Some Scope"}
    assert AzureDevopsClient._is_builtin_identity(identity) is True


def test_is_builtin_identity_passes_real_aad_user() -> None:
    """Normal AAD user identities should not be filtered."""
    assert AzureDevopsClient._is_builtin_identity(MOCK_IDENTITY_EXPANDED) is False


def test_is_builtin_identity_passes_real_msa_user() -> None:
    """MSA user identities should not be filtered."""
    identity = {
        "subjectDescriptor": "msa.xyz",
        "providerDisplayName": "Jane Doe",
    }
    assert AzureDevopsClient._is_builtin_identity(identity) is False


# ── _extract_project_entitlements ─────────────────────────────────────────────


def test_extract_project_entitlements_maps_scope_to_project() -> None:
    """Groups whose scopeId matches a project produce a projectEntitlements entry."""
    projects_by_id = {p["id"]: p for p in MOCK_PROJECTS}
    result = AzureDevopsClient._extract_project_entitlements(
        [MOCK_GROUP_IDENTITY_PROJECT_A], projects_by_id
    )
    assert len(result) == 1
    assert result[0]["projectRef"]["id"] == "proj-a-guid"
    assert result[0]["projectRef"]["name"] == "Project A"


def test_extract_project_entitlements_deduplicates_same_project() -> None:
    """Multiple groups in the same project yield only one projectEntitlements entry."""
    duplicate_group = {**MOCK_GROUP_IDENTITY_PROJECT_A, "subjectDescriptor": "vssgp.other"}
    projects_by_id = {p["id"]: p for p in MOCK_PROJECTS}
    result = AzureDevopsClient._extract_project_entitlements(
        [MOCK_GROUP_IDENTITY_PROJECT_A, duplicate_group], projects_by_id
    )
    assert len(result) == 1


def test_extract_project_entitlements_skips_unknown_scope() -> None:
    """Group identities whose scopeId does not match any project are silently skipped."""
    projects_by_id = {p["id"]: p for p in MOCK_PROJECTS}
    result = AzureDevopsClient._extract_project_entitlements(
        [MOCK_GROUP_IDENTITY_NO_SCOPE], projects_by_id
    )
    assert result == []


def test_extract_project_entitlements_empty_member_of() -> None:
    """Empty memberOf list produces an empty projectEntitlements list."""
    projects_by_id = {p["id"]: p for p in MOCK_PROJECTS}
    result = AzureDevopsClient._extract_project_entitlements([], projects_by_id)
    assert result == []


# ── _build_user_shape_from_graph_user ─────────────────────────────────────────


def test_build_user_shape_has_required_fields() -> None:
    """The envelope must contain user.*, id, accessLevel, and projectEntitlements."""
    shaped = AzureDevopsClient._build_user_shape_from_graph_user(MOCK_GRAPH_USER, [])
    assert shaped["user"]["mailAddress"] == "alice@example.com"
    assert shaped["user"]["displayName"] == "Alice Example"
    assert shaped["user"]["principalName"] == "alice@example.com"
    assert shaped["user"]["descriptor"] == "aad.abc123"
    assert shaped["id"] == "aaaa-bbbb-cccc-dddd"
    assert "accessLevel" in shaped
    assert shaped["projectEntitlements"] == []


def test_build_user_shape_access_level_fields_are_null() -> None:
    """accessLevel fields must be None (license info not available without PCA)."""
    shaped = AzureDevopsClient._build_user_shape_from_graph_user(MOCK_GRAPH_USER, [])
    assert shaped["accessLevel"]["accountLicenseType"] is None
    assert shaped["accessLevel"]["licenseDisplayName"] is None
    assert shaped["accessLevel"]["status"] is None


def test_build_user_shape_includes_project_entitlements() -> None:
    """projectEntitlements list is passed through to the output envelope."""
    entitlements = [{"projectRef": {"id": "proj-a-guid", "name": "Project A"}}]
    shaped = AzureDevopsClient._build_user_shape_from_graph_user(
        MOCK_GRAPH_USER, entitlements
    )
    assert shaped["projectEntitlements"] == entitlements


def test_build_user_shape_id_falls_back_to_descriptor() -> None:
    """When originId is absent, id falls back to the Graph descriptor."""
    user_no_origin = {**MOCK_GRAPH_USER, "originId": None}
    shaped = AzureDevopsClient._build_user_shape_from_graph_user(user_no_origin, [])
    assert shaped["id"] == "aad.abc123"


# ── _fetch_identities_for_descriptors ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_identities_batches_at_max_per_request() -> None:
    """More than MAX_IDENTITIES_PER_REQUEST descriptors must be split into two calls."""
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)
    descriptors = [f"aad.user{i}" for i in range(MAX_IDENTITIES_PER_REQUEST + 1)]

    mock_response = MagicMock()
    mock_response.json.return_value = {"value": []}

    with patch.object(client, "send_request", return_value=mock_response) as mock_send:
        await client._fetch_identities_for_descriptors(descriptors)
        assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_fetch_identities_handles_none_response() -> None:
    """None response from send_request must not raise and must return partial results."""
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)

    with patch.object(client, "send_request", return_value=None):
        result = await client._fetch_identities_for_descriptors(["aad.user1"])
    assert result == []


@pytest.mark.asyncio
async def test_fetch_identities_passes_query_membership_param() -> None:
    """The queryMembership parameter must be forwarded to the API call."""
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)

    mock_response = MagicMock()
    mock_response.json.return_value = {"value": [MOCK_IDENTITY_EXPANDED]}

    with patch.object(client, "send_request", return_value=mock_response) as mock_send:
        await client._fetch_identities_for_descriptors(
            ["aad.abc123"], query_membership="expandedUp"
        )
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["params"]["queryMembership"] == "expandedUp"


# ── generate_users_via_identities ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_users_via_identities_yields_shaped_users(
    mock_event_context: MagicMock,
) -> None:
    """Normal users must be yielded as entitlement-envelope dicts."""
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)

    async def mock_enumerate_graph_users() -> (
        AsyncGenerator[List[Dict[str, Any]], None]
    ):
        yield [MOCK_GRAPH_USER]

    async def mock_build_project_scope_map() -> Dict[str, Any]:
        return {p["id"]: p for p in MOCK_PROJECTS}

    with (
        patch.object(
            client, "_enumerate_graph_users", side_effect=mock_enumerate_graph_users
        ),
        patch.object(
            client,
            "_fetch_identities_for_descriptors",
            side_effect=[
                [MOCK_IDENTITY_EXPANDED],  # first call: user identities
                [MOCK_GROUP_IDENTITY_PROJECT_A, MOCK_GROUP_IDENTITY_PROJECT_B],  # group resolve
            ],
        ),
        patch.object(
            client, "_build_project_scope_map", side_effect=mock_build_project_scope_map
        ),
    ):
        users: List[Dict[str, Any]] = []
        async for batch in client.generate_users_via_identities():
            users.extend(batch)

    assert len(users) == 1
    assert users[0]["user"]["mailAddress"] == "alice@example.com"
    assert users[0]["user"]["displayName"] == "Alice Example"


@pytest.mark.asyncio
async def test_generate_users_via_identities_filters_builtins(
    mock_event_context: MagicMock,
) -> None:
    """Built-in identities ([TEAM FOUNDATION]\\...) must be excluded from output."""
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)

    async def mock_enumerate() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [MOCK_GRAPH_USER, MOCK_BUILTIN_GRAPH_USER]

    async def mock_project_map() -> Dict[str, Any]:
        return {}

    with (
        patch.object(client, "_enumerate_graph_users", side_effect=mock_enumerate),
        patch.object(
            client,
            "_fetch_identities_for_descriptors",
            side_effect=[
                [MOCK_IDENTITY_EXPANDED, MOCK_BUILTIN_IDENTITY],
                [],  # group resolve (empty)
            ],
        ),
        patch.object(client, "_build_project_scope_map", side_effect=mock_project_map),
    ):
        users: List[Dict[str, Any]] = []
        async for batch in client.generate_users_via_identities():
            users.extend(batch)

    assert len(users) == 1
    assert users[0]["user"]["mailAddress"] == "alice@example.com"


@pytest.mark.asyncio
async def test_generate_users_via_identities_resolves_project_membership(
    mock_event_context: MagicMock,
) -> None:
    """Users whose groups map to known projects must have projectEntitlements populated."""
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)

    async def mock_enumerate() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [MOCK_GRAPH_USER]

    async def mock_project_map() -> Dict[str, Any]:
        return {p["id"]: p for p in MOCK_PROJECTS}

    with (
        patch.object(client, "_enumerate_graph_users", side_effect=mock_enumerate),
        patch.object(
            client,
            "_fetch_identities_for_descriptors",
            side_effect=[
                [MOCK_IDENTITY_EXPANDED],
                [MOCK_GROUP_IDENTITY_PROJECT_A, MOCK_GROUP_IDENTITY_PROJECT_B],
            ],
        ),
        patch.object(client, "_build_project_scope_map", side_effect=mock_project_map),
    ):
        users: List[Dict[str, Any]] = []
        async for batch in client.generate_users_via_identities():
            users.extend(batch)

    assert len(users) == 1
    entitlements = users[0]["projectEntitlements"]
    project_ids = {e["projectRef"]["id"] for e in entitlements}
    assert "proj-a-guid" in project_ids
    assert "proj-b-guid" in project_ids


@pytest.mark.asyncio
async def test_generate_users_via_identities_handles_empty_graph_batch(
    mock_event_context: MagicMock,
) -> None:
    """Batches with no descriptors must be skipped without any API calls."""
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)

    async def mock_enumerate() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield []  # empty batch

    async def mock_project_map() -> Dict[str, Any]:
        return {}

    with (
        patch.object(client, "_enumerate_graph_users", side_effect=mock_enumerate),
        patch.object(
            client, "_fetch_identities_for_descriptors", new_callable=AsyncMock
        ) as mock_fetch,
        patch.object(client, "_build_project_scope_map", side_effect=mock_project_map),
    ):
        users: List[Dict[str, Any]] = []
        async for batch in client.generate_users_via_identities():
            users.extend(batch)

    assert users == []
    mock_fetch.assert_not_called()
