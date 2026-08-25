from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from github.clients.auth.abstract_authenticator import GitHubHeaders, GitHubToken
from github.probe import permissions
from port_ocean.core.probe import ProbeStatus


@pytest.mark.asyncio
async def test_app_permissions_are_mapped_only_to_available_kinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticator = SimpleNamespace(
        organization="port-labs",
        get_token=AsyncMock(
            return_value=GitHubToken(
                token="token",
                permissions={"metadata": "read", "issues": "write"},
            )
        ),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: True,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(
        ["repository", "issue", "code-scanning-alerts"]
    )

    assert [check.status for check in checks] == [
        ProbeStatus.SUCCESS,
        ProbeStatus.SUCCESS,
        ProbeStatus.FAILURE,
    ]
    assert [check.kind for check in checks] == [
        "repository",
        "issue",
        "code-scanning-alerts",
    ]
    assert all(check.scopes == {} for check in checks)


@pytest.mark.asyncio
async def test_app_checks_include_org_scopes_when_probing_multiple_installations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticators = [
        SimpleNamespace(
            organization="port-labs",
            get_token=AsyncMock(
                return_value=GitHubToken(
                    token="token-1",
                    permissions={"metadata": "read"},
                )
            ),
        ),
        SimpleNamespace(
            organization="port-team",
            get_token=AsyncMock(
                return_value=GitHubToken(
                    token="token-2",
                    permissions={"metadata": "read"},
                )
            ),
        ),
    ]
    provider = SimpleNamespace(
        is_app_auth=lambda: True,
        list_authenticators=AsyncMock(return_value=authenticators),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(["repository"])

    assert [check.kind for check in checks] == ["repository", "repository"]
    assert [check.scopes for check in checks] == [
        {"org": "port-labs"},
        {"org": "port-team"},
    ]


@pytest.mark.asyncio
async def test_missing_app_permissions_are_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticator = SimpleNamespace(
        organization="port-labs",
        get_token=AsyncMock(return_value=GitHubToken(token="token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: True,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(["repository"])

    assert checks[0].status == ProbeStatus.UNKNOWN
    assert checks[0].kind == "repository"
    assert checks[0].scopes == {}


@pytest.mark.asyncio
async def test_classic_pat_scopes_are_mapped_to_available_kinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        headers={"X-OAuth-Scopes": "repo, read:org"},
        request=httpx.Request("GET", "https://api.github.com/user"),
    )
    authenticator = SimpleNamespace(
        organization="port-labs",
        client=SimpleNamespace(get=AsyncMock(return_value=response)),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(
        ["repository", "team", "package"]
    )

    assert [check.status for check in checks] == [
        ProbeStatus.SUCCESS,
        ProbeStatus.SUCCESS,
        ProbeStatus.FAILURE,
    ]
    assert [check.kind for check in checks] == ["repository", "team", "package"]
    assert all(check.scopes == {} for check in checks)


@pytest.mark.asyncio
async def test_classic_pat_repo_scope_implies_security_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        headers={"X-OAuth-Scopes": "repo"},
        request=httpx.Request("GET", "https://api.github.com/user"),
    )
    authenticator = SimpleNamespace(
        organization="port-labs",
        client=SimpleNamespace(get=AsyncMock(return_value=response)),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(
        ["repository", "dependabot-alert", "code-scanning-alerts"]
    )

    assert [check.status for check in checks] == [
        ProbeStatus.SUCCESS,
        ProbeStatus.SUCCESS,
        ProbeStatus.SUCCESS,
    ]


@pytest.mark.asyncio
async def test_unscoped_pat_checks_include_discovered_org_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope_response = httpx.Response(
        200,
        headers={"X-OAuth-Scopes": "repo"},
        request=httpx.Request("GET", "https://api.github.com/user"),
    )
    organizations_response = httpx.Response(
        200,
        json=[{"login": "port-labs"}, {"login": "port-team"}],
        request=httpx.Request("GET", "https://api.github.com/user/orgs"),
    )
    authenticator = SimpleNamespace(
        organization=None,
        client=SimpleNamespace(
            get=AsyncMock(side_effect=[scope_response, organizations_response])
        ),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(["repository"])

    assert [check.kind for check in checks] == ["repository", "repository"]
    assert [check.scopes for check in checks] == [
        {"org": "port-labs"},
        {"org": "port-team"},
    ]


@pytest.mark.asyncio
async def test_single_discovered_pat_org_omits_scope_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope_response = httpx.Response(
        200,
        headers={"X-OAuth-Scopes": "repo"},
        request=httpx.Request("GET", "https://api.github.com/user"),
    )
    organizations_response = httpx.Response(
        200,
        json=[{"login": "port-labs"}],
        request=httpx.Request("GET", "https://api.github.com/user/orgs"),
    )
    authenticator = SimpleNamespace(
        organization=None,
        client=SimpleNamespace(
            get=AsyncMock(side_effect=[scope_response, organizations_response])
        ),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(["repository"])

    assert len(checks) == 1
    assert checks[0].scopes == {}


@pytest.mark.asyncio
async def test_pat_organization_discovery_follows_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope_response = httpx.Response(
        200,
        headers={"X-OAuth-Scopes": "repo"},
        request=httpx.Request("GET", "https://api.github.com/user"),
    )
    first_page = httpx.Response(
        200,
        json=[{"login": "port-labs"}],
        headers={"Link": ('<https://api.github.com/user/orgs?page=2>; rel="next"')},
        request=httpx.Request("GET", "https://api.github.com/user/orgs"),
    )
    second_page = httpx.Response(
        200,
        json=[{"login": "port-team"}],
        request=httpx.Request("GET", "https://api.github.com/user/orgs?page=2"),
    )
    authenticator = SimpleNamespace(
        organization=None,
        client=SimpleNamespace(
            get=AsyncMock(side_effect=[scope_response, first_page, second_page])
        ),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(["repository"])

    assert [check.scopes for check in checks] == [
        {"org": "port-labs"},
        {"org": "port-team"},
    ]


@pytest.mark.asyncio
async def test_fine_grained_pat_permissions_are_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope_response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://api.github.com/user"),
    )
    organizations_response = httpx.Response(
        200,
        json=[],
        request=httpx.Request("GET", "https://api.github.com/user/orgs"),
    )
    authenticator = SimpleNamespace(
        organization=None,
        client=SimpleNamespace(
            get=AsyncMock(side_effect=[scope_response, organizations_response])
        ),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    checks = await permissions.probe_github_permissions(["repository", "issue"])

    assert [check.status for check in checks] == [
        ProbeStatus.UNKNOWN,
        ProbeStatus.UNKNOWN,
    ]
    assert [check.kind for check in checks] == ["repository", "issue"]
    assert all(check.scopes == {} for check in checks)
