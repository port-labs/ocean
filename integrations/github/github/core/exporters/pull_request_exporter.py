from github.helpers.utils import enrich_with_repository, extract_repo_params
from github.helpers.exceptions import CheckRunsException
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient
from datetime import datetime, timezone


class RestPullRequestExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT,) -> RAW_ITEM:
        repo_name, params = extract_repo_params(dict(options))
        pr_number = params["pr_number"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls/{pr_number}"
        response = await self.client.send_api_request(endpoint)

        logger.debug(f"Fetched pull request with identifier: {repo_name}/{pr_number}")

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        repo_name, params = extract_repo_params(dict(options))

        endpoint = (
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls"
        )

        async for pull_requests in self.client.send_paginated_request(endpoint, params):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_name}"
            )
            batch = [enrich_with_repository(pr, repo_name) for pr in pull_requests]
            yield batch

    async def create_validation_check(self, repo_name: str, head_sha: str) -> str:
        """Create a new check run for validation."""
        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/check-runs"

        payload = {
            "name": "File Kind validation",
            "head_sha": head_sha,
            "status": "in_progress",
            "output": {
                "title": "Validating file kind changes",
                "summary": "Checking if file kind changes are valid according to Port configuration.",
            },
        }

        response = await self.client.send_api_request(
            endpoint, method="POST", json_data=payload
        )
        if not response:
            log_message = f"Failed to create check run for {repo_name}"
            logger.error(log_message)
            raise CheckRunsException(log_message)

        check_run_id = response["id"]

        logger.info(f"Created check run {check_run_id} for {repo_name}")

        return str(check_run_id)

    async def update_check_run(
        self,
        repo_name: str,
        check_run_id: str,
        status: str,
        conclusion: str,
        title: str,
        summary: str,
        details: str,
    ) -> None:
        """Update check run with results."""
        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/check-runs/{check_run_id}"

        payload = {
            "status": status,
            "conclusion": conclusion,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "output": {"title": title, "summary": summary, "text": details},
        }

        await self.client.send_api_request(endpoint, method="PATCH", json_data=payload)

        logger.info(
            f"Updated check run {check_run_id} for {repo_name} with {conclusion} status"
        )
