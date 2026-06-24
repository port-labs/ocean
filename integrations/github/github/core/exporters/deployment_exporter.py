import asyncio
import functools
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
    get_commit,
    parse_timestamp,
    build_first_commit,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from loguru import logger
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions


BATCH_CONCURRENCY_LIMIT = 10


def _created_at_sort_key(deployment: dict[str, Any]) -> datetime:
    parsed = parse_timestamp(deployment.get("created_at", ""))
    return parsed if parsed is not None else datetime.min.replace(tzinfo=timezone.utc)


def _earliest_commit(commits: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    earliest: Optional[dict[str, Any]] = None
    earliest_at: Optional[datetime] = None
    for commit in commits:
        parsed = parse_timestamp(commit["commit"]["committer"]["date"])
        if parsed is None:
            continue
        if earliest_at is None or parsed < earliest_at:
            earliest_at, earliest = parsed, commit
    return earliest


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
        return self._enrich_deployment(response, cast(str, repo_name), organization)

    async def get_paginated_resources[
        ExporterOptionsT: ListDeploymentsOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all deployments for a repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))
        repo = cast(str, repo_name)
        enrich_first_commit = bool(params.pop("enrich_with_first_commit", False))
        endpoint = f"{self.client.base_url}/repos/{organization}/{repo}/deployments"

        if not enrich_first_commit:
            async for deployments in self.client.send_paginated_request(
                endpoint, params
            ):
                logger.info(
                    f"Fetched batch of {len(deployments)} deployments from repository {repo} from {organization}"
                )
                yield [
                    self._enrich_deployment(deployment, repo, organization)
                    for deployment in deployments
                ]
            return

        deployments = [
            self._enrich_deployment(deployment, repo, organization)
            async for batch in self.client.send_paginated_request(endpoint, params)
            for deployment in batch
        ]
        if not deployments:
            return
        async for enriched in self._stream_first_commit_enrichment(
            organization, repo, deployments
        ):
            yield enriched

    async def _stream_first_commit_enrichment(
        self, organization: str, repo_name: str, deployments: list[dict[str, Any]]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info(
            f"Enriching {len(deployments)} deployments with first commit from repository {repo_name} from {organization}"
        )
        semaphore = asyncio.BoundedSemaphore(BATCH_CONCURRENCY_LIMIT)
        streams = [
            semaphore_async_iterator(
                semaphore,
                functools.partial(
                    self._stream_first_commit,
                    organization,
                    repo_name,
                    deployment,
                    predecessor_sha,
                ),
            )
            for deployment, predecessor_sha in self._pair_predecessors(deployments)
        ]
        async for enriched in stream_async_iterators_tasks(*streams):
            yield enriched

    def _enrich_deployment(
        self, deployment: dict[str, Any], repo_name: str, organization: str
    ) -> dict[str, Any]:
        return enrich_with_organization(
            enrich_with_repository(deployment, repo_name), organization
        )

    def _pair_predecessors(
        self, deployments: list[dict[str, Any]]
    ) -> list[tuple[dict[str, Any], Optional[str]]]:
        by_environment: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for deployment in deployments:
            by_environment[deployment.get("environment")].append(deployment)

        pairs: list[tuple[dict[str, Any], Optional[str]]] = []
        for environment_deployments in by_environment.values():
            ordered = sorted(
                environment_deployments, key=_created_at_sort_key, reverse=True
            )
            for index, deployment in enumerate(ordered):
                predecessor = ordered[index + 1] if index + 1 < len(ordered) else None
                pairs.append(
                    (deployment, predecessor.get("sha") if predecessor else None)
                )
        return pairs

    async def _stream_first_commit(
        self,
        organization: str,
        repo_name: str,
        deployment: dict[str, Any],
        predecessor_sha: Optional[str],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [
            await self._attach_first_commit(
                organization, repo_name, deployment, predecessor_sha
            )
        ]

    async def _attach_first_commit(
        self,
        organization: str,
        repo_name: str,
        deployment: dict[str, Any],
        predecessor_sha: Optional[str],
    ) -> dict[str, Any]:
        # Must never raise: a failure would abort the whole merged stream.
        deployment_sha = deployment.get("sha")
        if not deployment_sha:
            return deployment
        try:
            resolved = await self._resolve_first_commit(
                organization, repo_name, predecessor_sha, deployment_sha
            )
            if resolved:
                first_commit, commit_count = resolved
                deployment["__firstCommit"] = first_commit
                deployment["__commitCount"] = commit_count
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
    ) -> Optional[tuple[dict[str, Any], int]]:
        if predecessor_sha and predecessor_sha != deployment_sha:
            comparison = await fetch_commit_diff(
                self.client, organization, repo_name, predecessor_sha, deployment_sha
            )
            commits = [
                commit
                for commit in comparison.get("commits", [])
                if commit.get("commit", {}).get("committer", {}).get("date")
            ]
            if len(commits):
                earliest = _earliest_commit(commits)
                if earliest is not None:
                    count = comparison.get("total_commits") or len(commits)
                    return (
                        build_first_commit(
                            earliest,
                            earliest.get("sha"),
                            earliest["commit"]["committer"]["date"],
                        ),
                        count,
                    )

        commit = await get_commit(self.client, organization, repo_name, deployment_sha)
        date = (commit.get("commit") or {}).get("committer", {}).get("date")
        if date and parse_timestamp(date) is not None:
            return (
                build_first_commit(commit, commit.get("sha") or deployment_sha, date),
                1,
            )
        return None
