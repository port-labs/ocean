from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from github.clients.auth.abstract_authenticator import GitHubHeaders, GitHubToken
from github.helpers.exceptions import AuthenticationException
from github.probe import GitHubPermissionProbe
from github.probe import permissions
from port_ocean.core.probe import ProbeCheckStatus, ProbeContext, ProbeStatus


async def _run_probe(
    monkeypatch: pytest.MonkeyPatch,
    kinds: list[str],
    provider: object,
) -> ProbeContext:
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)
    context = ProbeContext()
    context.available_kinds = kinds
    await GitHubPermissionProbe(context).run()
    return context


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

    context = await _run_probe(
        monkeypatch,
        ["repository", "issue", "code-scanning-alerts"],
        provider,
    )
    checks = context.checks

    assert [check.status for check in checks] == [
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.FAILURE,
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

    context = await _run_probe(monkeypatch, ["repository"], provider)
    checks = context.checks

    assert [check.kind for check in checks] == ["repository", "repository"]
    assert [check.scopes for check in checks] == [
        {"org": "port-labs"},
        {"org": "port-team"},
    ]


@pytest.mark.asyncio
async def test_all_checks_are_published_as_pending_before_being_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticators = [
        SimpleNamespace(
            organization=organization,
            get_token=AsyncMock(
                return_value=GitHubToken(
                    token="token",
                    permissions={"metadata": "read", "issues": "read"},
                )
            ),
        )
        for organization in ("port-labs", "port-team")
    ]
    provider = SimpleNamespace(
        is_app_auth=lambda: True,
        list_authenticators=AsyncMock(return_value=authenticators),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)

    context = ProbeContext()
    context.available_kinds = ["repository", "issue"]
    snapshots: list[list[ProbeCheckStatus]] = []
    monkeypatch.setattr(
        context,
        "update_progress",
        MagicMock(
            side_effect=lambda: snapshots.append(
                [check.status for check in context.checks]
            )
        ),
    )

    await GitHubPermissionProbe(context).run()

    assert snapshots[0] == [ProbeCheckStatus.PENDING] * 4
    assert snapshots[-1] == [
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.SUCCESS,
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

    context = await _run_probe(monkeypatch, ["repository"], provider)
    checks = context.checks

    assert checks[0].status == ProbeCheckStatus.UNKNOWN
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

    context = await _run_probe(monkeypatch, ["repository", "team", "package"], provider)
    checks = context.checks

    assert [check.status for check in checks] == [
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.FAILURE,
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

    context = await _run_probe(
        monkeypatch,
        ["repository", "dependabot-alert", "code-scanning-alerts"],
        provider,
    )

    assert [check.status for check in context.checks] == [
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.SUCCESS,
        ProbeCheckStatus.SUCCESS,
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
            get=AsyncMock(side_effect=[organizations_response, scope_response])
        ),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )

    context = await _run_probe(monkeypatch, ["repository"], provider)
    checks = context.checks

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
            get=AsyncMock(side_effect=[organizations_response, scope_response])
        ),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )

    context = await _run_probe(monkeypatch, ["repository"], provider)

    assert len(context.checks) == 1
    assert context.checks[0].scopes == {}


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
            get=AsyncMock(side_effect=[first_page, second_page, scope_response])
        ),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )

    context = await _run_probe(monkeypatch, ["repository"], provider)

    assert [check.scopes for check in context.checks] == [
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
            get=AsyncMock(side_effect=[organizations_response, scope_response])
        ),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    provider = SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )

    context = await _run_probe(monkeypatch, ["repository", "issue"], provider)
    checks = context.checks

    assert [check.status for check in checks] == [
        ProbeCheckStatus.UNKNOWN,
        ProbeCheckStatus.UNKNOWN,
    ]
    assert [check.kind for check in checks] == ["repository", "issue"]
    assert all(check.scopes == {} for check in checks)


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.github.com/user")
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=httpx.Response(status_code, request=request),
    )


def _pat_provider(get_side_effect: object) -> SimpleNamespace:
    authenticator = SimpleNamespace(
        organization="port-labs",
        client=SimpleNamespace(get=AsyncMock(side_effect=get_side_effect)),
        get_headers=AsyncMock(return_value=GitHubHeaders(Authorization="Bearer token")),
    )
    return SimpleNamespace(
        is_app_auth=lambda: False,
        list_authenticators=AsyncMock(return_value=[authenticator]),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error, expected_message",
    [
        (
            _http_status_error(401),
            "GitHub rejected the configured credentials with HTTP 401",
        ),
        (
            _http_status_error(403),
            "GitHub rejected the configured credentials with HTTP 403",
        ),
        (
            _http_status_error(500),
            "GitHub returned HTTP 500 while probing permissions",
        ),
        (
            httpx.ConnectError("nodename nor servname provided"),
            "GitHub could not be reached while probing permissions: "
            "nodename nor servname provided",
        ),
    ],
)
async def test_failed_pat_lookup_fails_the_probe_with_a_reason(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected_message: str
) -> None:
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: _pat_provider(error))
    context = ProbeContext()
    context.available_kinds = ["repository", "issue"]

    await GitHubPermissionProbe(context).run()

    assert context.status is ProbeStatus.FAILED
    assert context.message == expected_message
    assert context.checks == []


@pytest.mark.asyncio
async def test_failed_app_token_fetch_fails_the_probe_with_a_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status_error = _http_status_error(401)

    async def get_token() -> GitHubToken:
        raise AuthenticationException(
            "Failed to fetch installation token: HTTP 401"
        ) from status_error

    provider = SimpleNamespace(
        is_app_auth=lambda: True,
        list_authenticators=AsyncMock(
            return_value=[
                SimpleNamespace(organization="port-labs", get_token=get_token)
            ]
        ),
    )
    monkeypatch.setattr(permissions, "get_auth_provider", lambda: provider)
    context = ProbeContext()
    context.available_kinds = ["repository"]

    await GitHubPermissionProbe(context).run()

    assert context.status is ProbeStatus.FAILED
    assert context.message == "GitHub rejected the configured credentials with HTTP 401"
    assert context.checks == []
