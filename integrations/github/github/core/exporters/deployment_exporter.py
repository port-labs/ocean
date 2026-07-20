import asyncio
from collections import defaultdict
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
    created_at_sort_key,
    earliest_commit,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions


BATCH_CONCURRENCY_LIMIT = 10


class RestDeploymentExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleDeploymentOptions
    ](self, options: ExporterOptionsT) -> Optional[RAW_ITEM]:
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
                yield self._enrich_deployments(deployments, repo, organization)
            return

        pending: dict[Any, dict[str, Any]] = {}
        async for deployments in self.client.send_paginated_request(endpoint, params):
            pairs, pending = self._pair_predecessors(deployments, pending)
            enriched = await self._enrich_first_commits(organization, repo, pairs)
            if enriched:
                yield self._enrich_deployments(enriched, repo, organization)

        if pending:
            enriched = await self._enrich_first_commits(
                organization,
                repo,
                [(deployment, None) for deployment in pending.values()],
            )
            if enriched:
                yield self._enrich_deployments(enriched, repo, organization)

    def _enrich_deployment(
        self, deployment: dict[str, Any], repo_name: str, organization: str
    ) -> dict[str, Any]:
        return enrich_with_organization(
            enrich_with_repository(deployment, repo_name), organization
        )

    def _enrich_deployments(
        self, deployments: list[dict[str, Any]], repo_name: str, organization: str
    ) -> list[dict[str, Any]]:
        return [
            self._enrich_deployment(deployment, repo_name, organization)
            for deployment in deployments
        ]

    async def _enrich_first_commits(
        self,
        organization: str,
        repo_name: str,
        pairs: list[tuple[dict[str, Any], Optional[str]]],
    ) -> list[dict[str, Any]]:
        if not pairs:
            return []

        logger.info(
            f"Enriching {len(pairs)} deployments with first commit from repository {repo_name} from {organization}"
        )
        semaphore = asyncio.BoundedSemaphore(BATCH_CONCURRENCY_LIMIT)

        async def enrich(
            deployment: dict[str, Any], predecessor_sha: Optional[str]
        ) -> dict[str, Any]:
            async with semaphore:
                return await self._attach_first_commit(
                    organization, repo_name, deployment, predecessor_sha
                )

        return await asyncio.gather(
            *(
                enrich(deployment, predecessor_sha)
                for deployment, predecessor_sha in pairs
            )
        )

    def _pair_predecessors(
        self,
        deployments: list[dict[str, Any]],
        pending: dict[Any, dict[str, Any]],
    ) -> tuple[list[tuple[dict[str, Any], Optional[str]]], dict[Any, dict[str, Any]]]:
        grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for deployment in deployments:
            grouped[deployment.get("environment")].append(deployment)

        pairs: list[tuple[dict[str, Any], Optional[str]]] = []
        next_pending = dict(pending)
        for environment, environment_deployments in grouped.items():
            ordered = sorted(
                environment_deployments, key=created_at_sort_key, reverse=True
            )
            previous_page_tail = next_pending.pop(environment, None)
            if previous_page_tail is not None:
                pairs.append((previous_page_tail, ordered[0].get("sha")))
            pairs.extend(
                (current, previous.get("sha"))
                for current, previous in zip(ordered, ordered[1:])
            )
            next_pending[environment] = ordered[-1]
        return pairs, next_pending

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
            resolved = await self._first_commit_from_comparison(
                organization, repo_name, predecessor_sha, deployment_sha
            )
            if resolved is None:
                resolved = await self._first_commit_from_sha(
                    organization, repo_name, deployment_sha
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

    async def _first_commit_from_comparison(
        self,
        organization: str,
        repo_name: str,
        predecessor_sha: Optional[str],
        deployment_sha: str,
    ) -> Optional[tuple[dict[str, Any], int]]:
        if not predecessor_sha or predecessor_sha == deployment_sha:
            return None

        comparison = await fetch_commit_diff(
            self.client, organization, repo_name, predecessor_sha, deployment_sha
        )
        commits = comparison.get("commits", [])
        earliest = earliest_commit(commits)
        if earliest is None:
            return None

        commit_count = comparison.get("total_commits") or len(commits)
        return (
            build_first_commit(
                earliest,
                earliest.get("sha"),
                earliest["commit"]["committer"]["date"],
            ),
            commit_count,
        )

    async def _first_commit_from_sha(
        self,
        organization: str,
        repo_name: str,
        deployment_sha: str,
    ) -> Optional[tuple[dict[str, Any], int]]:
        commit = await get_commit(self.client, organization, repo_name, deployment_sha)
        date = commit.get("commit", {}).get("committer", {}).get("date")
        if not date or parse_timestamp(date) is None:
            return None

        return (
            build_first_commit(commit, commit.get("sha") or deployment_sha, date),
            1,
        )
