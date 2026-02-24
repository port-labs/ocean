"""Unit tests for vercel/client.py."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import pytest
import pytest_httpx

from client import VercelClient, PAGE_LIMIT


# ── Fixture helpers ────────────────────────────────────────────────────────────


def _paginated_response(
    items: list[dict[str, Any]],
    key: str,
    next_cursor: int | None = None,
) -> dict[str, Any]:
    """Build a mock Vercel paginated API response."""
    pagination: dict[str, Any] = {"count": len(items)}
    if next_cursor is not None:
        pagination["next"] = next_cursor
    return {key: items, "pagination": pagination}


# ── Team tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_teams_personal(
    httpx_mock: pytest_httpx.HTTPXMock,
    vercel_token: str,
    sample_team: dict[str, Any],
) -> None:
    """When no teamId is set, /v2/teams is fetched and all pages yielded."""
    httpx_mock.add_response(
        url=f"https://api.vercel.com/v2/teams?limit={PAGE_LIMIT}",
        json=_paginated_response([sample_team], "teams"),
    )

    async with VercelClient(token=vercel_token) as client:
        pages = [p async for p in client.get_teams()]

    assert len(pages) == 1
    assert pages[0][0]["id"] == sample_team["id"]


@pytest.mark.asyncio
async def test_get_teams_scoped_to_team(
    httpx_mock: pytest_httpx.HTTPXMock,
    vercel_token: str,
    team_id: str,
    sample_team: dict[str, Any],
) -> None:
    """When teamId is set, the single-team endpoint is used."""
    httpx_mock.add_response(
        url=f"https://api.vercel.com/v2/teams/{team_id}",
        json=sample_team,
    )

    async with VercelClient(token=vercel_token, team_id=team_id) as client:
        pages = [p async for p in client.get_teams()]

    assert pages == [[sample_team]]


# ── Project tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_projects_attaches_team_id(
    httpx_mock: pytest_httpx.HTTPXMock,
    vercel_token: str,
    team_id: str,
    sample_project: dict[str, Any],
) -> None:
    """teamId should be injected into every project when client is team-scoped."""
    project_without_team = {**sample_project}
    del project_without_team["teamId"]

    httpx_mock.add_response(
        url=f"https://api.vercel.com/v9/projects?limit={PAGE_LIMIT}&teamId={team_id}",
        json=_paginated_response([project_without_team], "projects"),
    )

    async with VercelClient(token=vercel_token, team_id=team_id) as client:
        pages = [p async for p in client.get_projects()]

    assert pages[0][0]["teamId"] == team_id


# ── Deployment tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_deployments_for_project(
    httpx_mock: pytest_httpx.HTTPXMock,
    vercel_token: str,
    sample_deployment: dict[str, Any],
) -> None:
    """Deployments for a specific project are fetched correctly."""
    project_id = "prj_abc123"
    httpx_mock.add_response(
        url=(
            f"https://api.vercel.com/v6/deployments"
            f"?limit={PAGE_LIMIT}&projectId={project_id}"
        ),
        json=_paginated_response([sample_deployment], "deployments"),
    )

    async with VercelClient(token=vercel_token) as client:
        pages = [p async for p in client.get_deployments(project_id=project_id)]

    assert len(pages) == 1
    assert pages[0][0]["uid"] == sample_deployment["uid"]


# ── Domain tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_project_domains(
    httpx_mock: pytest_httpx.HTTPXMock,
    vercel_token: str,
    sample_domain: dict[str, Any],
) -> None:
    """Domains should have their projectId attached by the client."""
    project_id = "prj_abc123"
    domain_without_pid = {**sample_domain}
    del domain_without_pid["projectId"]

    httpx_mock.add_response(
        url=(
            f"https://api.vercel.com/v9/projects/{project_id}/domains"
            f"?limit={PAGE_LIMIT}"
        ),
        json=_paginated_response([domain_without_pid], "domains"),
    )

    async with VercelClient(token=vercel_token) as client:
        pages = [p async for p in client.get_project_domains(project_id)]

    assert pages[0][0]["projectId"] == project_id


# ── Pagination tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pagination_follows_cursor(
    httpx_mock: pytest_httpx.HTTPXMock,
    vercel_token: str,
    sample_project: dict[str, Any],
) -> None:
    """The client should follow ``pagination.next`` cursors until exhausted."""
    cursor = 1700005000000
    second_project = {**sample_project, "id": "prj_second", "name": "second-app"}

    httpx_mock.add_response(
        url=f"https://api.vercel.com/v9/projects?limit={PAGE_LIMIT}",
        json=_paginated_response([sample_project], "projects", next_cursor=cursor),
    )
    httpx_mock.add_response(
        url=f"https://api.vercel.com/v9/projects?limit={PAGE_LIMIT}&until={cursor}",
        json=_paginated_response([second_project], "projects"),
    )

    async with VercelClient(token=vercel_token) as client:
        pages = [p async for p in client.get_projects()]

    assert len(pages) == 2
    assert pages[1][0]["id"] == "prj_second"


# ── get_all_projects_flat tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_projects_flat_yields_individual_dicts(
    httpx_mock: pytest_httpx.HTTPXMock,
    vercel_token: str,
    sample_project: dict[str, Any],
) -> None:
    """get_all_projects_flat should yield individual project dicts, not pages."""
    second_project = {**sample_project, "id": "prj_second", "name": "second-app"}

    httpx_mock.add_response(
        url=f"https://api.vercel.com/v9/projects?limit={PAGE_LIMIT}",
        json=_paginated_response([sample_project, second_project], "projects"),
    )

    async with VercelClient(token=vercel_token) as client:
        projects = [p async for p in client.get_all_projects_flat()]

    assert len(projects) == 2
    assert projects[0]["id"] == sample_project["id"]
    assert projects[1]["id"] == "prj_second"
    # Each item should be a dict, not a list (i.e. not a page).
    assert isinstance(projects[0], dict)


# ── Webhook signature tests ────────────────────────────────────────────────────


def test_verify_webhook_signature_valid() -> None:
    secret = "mysecret"
    payload = b'{"type":"deployment.created"}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha1).hexdigest()
    assert VercelClient.verify_webhook_signature(payload, sig, secret) is True


def test_verify_webhook_signature_invalid() -> None:
    secret = "mysecret"
    payload = b'{"type":"deployment.created"}'
    assert VercelClient.verify_webhook_signature(payload, "badsig", secret) is False
