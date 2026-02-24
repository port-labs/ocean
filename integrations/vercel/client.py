"""
Async Vercel REST API client.

Handles authentication and cursor-based pagination for all resources
surfaced by this Ocean integration (teams, projects, deployments, domains).

Vercel API docs: https://vercel.com/docs/rest-api
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, AsyncGenerator

import httpx
from port_ocean.context.ocean import ocean

logger = logging.getLogger(__name__)

VERCEL_BASE_URL = "https://api.vercel.com"
# Number of items to request per paginated page.
PAGE_LIMIT = 100


class VercelClient:
    """Thin async wrapper around the Vercel REST API."""

    def __init__(self, token: str, team_id: str | None = None) -> None:
        self.token = token
        self.team_id = team_id
        self._client: httpx.AsyncClient | None = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def __aenter__(self) -> "VercelClient":
        self._client = httpx.AsyncClient(
            base_url=VERCEL_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    # ── internal helpers ───────────────────────────────────────────────────

    def _team_params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build query-param dict, injecting teamId when configured."""
        params: dict[str, Any] = {}
        if self.team_id:
            params["teamId"] = self.team_id
        if extra:
            params.update(extra)
        return params

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if self._client is None:
            raise RuntimeError("Client not initialised — use as async context manager")
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def _paginate(
        self,
        path: str,
        result_key: str,
        extra_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of results using Vercel's cursor-based pagination."""
        params = self._team_params({"limit": PAGE_LIMIT, **(extra_params or {})})
        while True:
            data = await self._get(path, params=params)
            items: list[dict[str, Any]] = data.get(result_key, [])
            if items:
                yield items

            pagination = data.get("pagination", {})
            next_cursor = pagination.get("next")
            if not next_cursor:
                break
            params["until"] = next_cursor

    # ── public API methods ─────────────────────────────────────────────────

    async def get_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Yield pages of teams the token has access to.

        Note: when a teamId is configured we still return that single team
        so the blueprint entity exists for relations.
        """
        if self.team_id:
            # Fetch the specific team only.
            data = await self._get(f"/v2/teams/{self.team_id}")
            yield [data]
        else:
            async for page in self._paginate("/v2/teams", "teams"):
                yield page

    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of projects (optionally scoped to a team)."""
        async for page in self._paginate("/v9/projects", "projects"):
            # Attach teamId to each project so we can resolve the relation later.
            if self.team_id:
                for project in page:
                    project.setdefault("teamId", self.team_id)
            yield page

    async def get_deployments(
        self,
        project_id: str | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Yield pages of deployments.

        When *project_id* is supplied only deployments for that project are
        returned.  The integration calls this once per project during a full
        resync.
        """
        extra: dict[str, Any] = {}
        if project_id:
            extra["projectId"] = project_id
        async for page in self._paginate(
            "/v6/deployments", "deployments", extra_params=extra
        ):
            yield page

    async def get_project_domains(
        self, project_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of custom domains attached to *project_id*."""
        async for page in self._paginate(
            f"/v9/projects/{project_id}/domains",
            "domains",
        ):
            # Attach projectId so we can resolve the relation in mapping.
            for domain in page:
                domain.setdefault("projectId", project_id)
            yield page

    async def get_all_projects_flat(self) -> AsyncGenerator[dict[str, Any], None]:
        """Convenience generator that yields individual project dicts."""
        async for page in self.get_projects():
            for project in page:
                yield project

    # ── webhook validation ─────────────────────────────────────────────────

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature_header: str,
        secret: str,
    ) -> bool:
        """
        Validate an incoming Vercel webhook payload against the HMAC-SHA1
        signature Vercel sends in the ``x-vercel-signature`` header.

        https://vercel.com/docs/observability/webhooks-overview/webhooks-api#securing-webhooks
        """
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha1,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)


def create_client() -> VercelClient:
    """Build a VercelClient from the current Ocean integration configuration."""
    cfg = ocean.integration_config
    return VercelClient(
        token=cfg["token"],
        team_id=cfg.get("teamId") or None,
    )
