import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import cast, Any, Optional
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
    fetch_commit_diff,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions


BATCH_CONCURRENCY_LIMIT = 10


def _parse_timestamp(timestamp: str) -> datetime:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return datetime.max.replace(tzinfo=timezone.utc)


class RestDeploymentExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleDeploymentOptions
    ](self, options: ExporterOptionsT) -> Optional[RAW_ITEM]:
        """Get a single deployment for a repository."""
        repo_name, organization, params = parse_github_options(dict(options))
        deployment_id = params["id"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/deployments/{deployment_id}"
        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No deployment found with identifier: {deployment_id} in repository: {repo_name} from {organization}"
            )
            return None

        logger.info(
            f"Fetched deployment with identifier {deployment_id} from repository {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )

    async def get_paginated_resources[
        ExporterOptionsT: ListDeploymentsOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all deployments for a repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))
        enrich_first_commit = bool(params.pop("enrich_with_first_commit", False))
        endpoint = (
            f"{self.client.base_url}/repos/{organization}/{repo_name}/deployments"
        )

        if not enrich_first_commit:
            async for deployments in self.client.send_paginated_request(
                endpoint, params
            ):
                logger.info(
                    f"Fetched batch of {len(deployments)} deployments from repository {repo_name} from {organization}"
                )
                yield [
                    enrich_with_organization(
                        enrich_with_repository(deployment, cast(str, repo_name)),
                        organization,
                    )
                    for deployment in deployments
                ]
            return

        buffered: list[dict[str, Any]] = []
        async for batch in self.client.send_paginated_request(endpoint, params):
            buffered.extend(
                enrich_with_organization(
                    enrich_with_repository(deployment, cast(str, repo_name)),
                    organization,
                )
                for deployment in batch
            )
        if buffered:
            logger.info(
                f"Enriching {len(buffered)} deployments with first commit from repository {repo_name} from {organization}"
            )
            yield await self._enrich_with_first_commit(
                organization, cast(str, repo_name), buffered
            )

    async def _enrich_with_first_commit(
        self, organization: str, repo_name: str, deployments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # GitHub's compare API needs the predecessor sha, so each deployment is paired with the
        # next-older deployment in the same environment. The list order GitHub returns is not
        # contracted, so sort by created_at rather than trusting it.
        by_environment: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for deployment in deployments:
            by_environment[deployment.get("environment")].append(deployment)

        semaphore = asyncio.Semaphore(BATCH_CONCURRENCY_LIMIT)
        tasks = []
        for environment_deployments in by_environment.values():
            ordered = sorted(
                environment_deployments,
                key=lambda deployment: _parse_timestamp(
                    deployment.get("created_at", "")
                ),
                reverse=True,
            )
            for index, deployment in enumerate(ordered):
                predecessor = ordered[index + 1] if index + 1 < len(ordered) else None
                tasks.append(
                    self._run_first_commit_enrichment(
                        organization,
                        repo_name,
                        deployment,
                        predecessor.get("sha") if predecessor else None,
                        semaphore,
                    )
                )
        return await asyncio.gather(*tasks)

    async def _run_first_commit_enrichment(
        self,
        organization: str,
        repo_name: str,
        deployment: dict[str, Any],
        predecessor_sha: Optional[str],
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any]:
        async with semaphore:
            return await self._attach_first_commit(
                organization, repo_name, deployment, predecessor_sha
            )

    async def _attach_first_commit(
        self,
        organization: str,
        repo_name: str,
        deployment: dict[str, Any],
        predecessor_sha: Optional[str],
    ) -> dict[str, Any]:
        deployment_sha = deployment.get("sha")
        if not deployment_sha:
            return deployment
        try:
            first_commit = await self._resolve_first_commit(
                organization, repo_name, predecessor_sha, deployment_sha
            )
            if first_commit:
                deployment["__firstCommit"] = first_commit
        except Exception as e:
            logger.warning(
                f"First-commit enrichment failed for deployment {deployment.get('id')}: {e}"
            )
        return deployment

    async def _resolve_first_commit(
        self,
        organization: str,
        repo_name: str,
        predecessor_sha: Optional[str],
        deployment_sha: str,
    ) -> Optional[dict[str, Any]]:
        if predecessor_sha and predecessor_sha != deployment_sha:
            comparison = await fetch_commit_diff(
                self.client, organization, repo_name, predecessor_sha, deployment_sha
            )
            commits = comparison.get("commits") or []
            timestamped = [
                commit
                for commit in commits
                if ((commit.get("commit") or {}).get("committer") or {}).get("date")
            ]
            if timestamped:
                earliest = min(
                    timestamped,
                    key=lambda commit: _parse_timestamp(
                        commit["commit"]["committer"]["date"]
                    ),
                )
                return {
                    **earliest,
                    "__sha": earliest.get("sha"),
                    "__timestamp": earliest["commit"]["committer"]["date"],
                    "__commitCount": comparison.get("total_commits") or len(commits),
                }

        commit = await self._get_commit(organization, repo_name, deployment_sha)
        committer = (commit.get("commit") or {}).get("committer") or {}
        if committer.get("date"):
            return {
                **commit,
                "__sha": commit.get("sha") or deployment_sha,
                "__timestamp": committer["date"],
                "__commitCount": 1,
            }
        return None

    async def _get_commit(
        self, organization: str, repo_name: str, sha: str
    ) -> dict[str, Any]:
        endpoint = (
            f"{self.client.base_url}/repos/{organization}/{repo_name}/commits/{sha}"
        )
        return await self.client.send_api_request(endpoint)
