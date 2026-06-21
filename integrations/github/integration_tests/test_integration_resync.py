from typing import Any

import httpx
import pytest
from port_ocean.integration_testing import InterceptTransport, ResyncResult

from _base import (
    GithubIntegrationTest,
    ORG_LOGIN,
    ORG_ID,
    README_TEXT,
    REPO_NAMES,
)


class TestGithubHappyPath(GithubIntegrationTest):
    """Happy-path integration test for the GitHub integration.

    Exercises the basic resync flow end-to-end:
    - GitHub App auth (installation lookup -> access token)
    - Organization fetch
    - Repository listing with included files (README, CODEOWNERS)
    - Pull request listing (open PRs only)

    Expected output:
    - 1 githubOrganization entity
    - 2 githubRepository entities (related to the org, README content populated)
    - 2 githubPullRequest entities (one per repo, related to the repo)
    """

    @pytest.mark.asyncio
    async def test_happy_path(self, resync: ResyncResult) -> None:
        assert resync.errors == [], f"Resync had errors: {resync.errors}"

        by_blueprint: dict[str, list[dict[str, Any]]] = {}
        for entity in resync.upserted_entities:
            by_blueprint.setdefault(entity["blueprint"], []).append(entity)

        # --- Organization ---
        orgs = by_blueprint.get("githubOrganization", [])
        assert len(orgs) == 1
        org = orgs[0]
        assert org["identifier"] == ORG_LOGIN
        assert org["properties"]["id"] == ORG_ID
        assert org["properties"]["login"] == ORG_LOGIN
        assert org["properties"]["description"] == "Test organization"

        # --- Repositories ---
        repos = by_blueprint.get("githubRepository", [])
        assert {e["identifier"] for e in repos} == set(REPO_NAMES)
        for repo in repos:
            props = repo["properties"]
            assert props["visibility"] == "public"
            assert props["defaultBranch"] == "main"
            assert props["language"] == "Python"
            assert props["readme"] == README_TEXT
            assert not props.get("codeowners"), "CODEOWNERS should be empty (404)"
            assert repo["relations"]["organization"] == ORG_LOGIN

        # --- Pull requests ---
        prs = by_blueprint.get("githubPullRequest", [])
        assert len(prs) == len(REPO_NAMES)
        for pr in prs:
            assert pr["properties"]["status"] == "open"
            assert pr["relations"]["repository"] in REPO_NAMES


class TestGithubPullRequestResyncPartialRepoFailure(GithubIntegrationTest):
    """When one repo's PR list request fails, others in the same page still export.

    Exercises ``resync_pull_requests`` handling of ``ExceptionGroup`` from
    ``stream_independent_async_iterators`` (e.g. intermittent 502 from GitHub).
    The harness uses the intercepted transport without GitHub's retry wrapper,
    so a single 502 response is enough to fail that repo's iterator quickly.
    """

    def customize_transport(self, t: InterceptTransport) -> None:
        # First repo's PR fetch fails with 502; second repo falls through to
        # the default 200 response from the base.
        t.add_route(
            "GET",
            f"/repos/{ORG_LOGIN}/{REPO_NAMES[0]}/pulls",
            {"status_code": 502, "json": {"message": "Bad Gateway"}},
        )

    @pytest.mark.asyncio
    async def test_pull_requests_still_exported_for_other_repos(self, resync: ResyncResult) -> None:
        prs = [e for e in resync.upserted_entities if e.get("blueprint") == "githubPullRequest"]
        assert len(prs) == 1
        assert prs[0]["relations"]["repository"] == REPO_NAMES[1]

        assert resync.reconciliation_success is False
        assert resync.errors, f"Expected resync errors after repo PR fetch failure, got {resync.errors}"

        def _walk_exceptions(exc: BaseException) -> list[BaseException]:
            out: list[BaseException] = [exc]
            if isinstance(exc, BaseExceptionGroup):
                for sub in exc.exceptions:
                    out.extend(_walk_exceptions(sub))
            if exc.__cause__ is not None:
                out.extend(_walk_exceptions(exc.__cause__))
            return out

        chain: list[BaseException] = []
        for err in resync.errors:
            chain.extend(_walk_exceptions(err))

        status_errors = [e for e in chain if isinstance(e, httpx.HTTPStatusError)]
        assert status_errors, f"Expected HTTPStatusError in __cause__ chain, got {chain!r}"
        assert any(e.response.status_code == 502 for e in status_errors)

        by_blueprint: dict[str, list[dict[str, Any]]] = {}
        for entity in resync.upserted_entities:
            by_blueprint.setdefault(entity["blueprint"], []).append(entity)

        assert len(by_blueprint.get("githubOrganization", [])) == 1
        assert len(by_blueprint.get("githubRepository", [])) == len(REPO_NAMES)
