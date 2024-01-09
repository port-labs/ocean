from typing import Any, AsyncGenerator, Optional
from urllib.parse import urlparse
import httpx

from loguru import logger

from port_ocean.context.event import event
from port_ocean.utils import http_async_client


class JenkinsClient:
    def __init__(
        self, jenkins_base_url: str, jenkins_user: str, jenkins_token: str
    ) -> None:
        self.jenkins_base_url = jenkins_base_url
        self.client = http_async_client
        self.client.auth = httpx.BasicAuth(jenkins_user, jenkins_token)

    async def get_all_jobs_and_builds(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        cache_key = "jenkins_jobs_and_builds"

        if cache := event.attributes.get(cache_key):
            logger.info("picking from cache")
            yield cache
            return

        async for jobs in self.fetch_jobs_and_builds_from_api():
            event.attributes.setdefault(cache_key, []).extend(jobs)
            yield jobs

    async def fetch_jobs_and_builds_from_api(
        self, parent_job: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        page_size = 5
        page = 0

        while True:
            params = self._build_api_params(page_size, page)
            base_url = self._build_base_url(parent_job)

            job_response = await self.client.get(f"{base_url}/api/json", params=params)
            job_response.raise_for_status()
            jobs = job_response.json()["jobs"]

            if not jobs:
                break

            yield await self._process_jobs(jobs, parent_job)

            page += 1

            if len(jobs) < page_size:
                break

    def _build_api_params(self, page_size: int, page: int) -> dict[str, Any]:
        start_idx = page_size * page
        end_idx = start_idx + page_size

        return {
            "tree": f"jobs[name,url,displayName,fullName,color,jobs[name,color,fullName,displayName,url],"
            f"builds[id,number,url,result,duration,timestamp,displayName,fullDisplayName]"
            f"{{0,50}}]{{{start_idx},{end_idx}}}"
        }

    def _build_base_url(self, parent_job: Optional[dict[str, Any]]) -> str:
        job_path = urlparse(parent_job["url"]).path if parent_job else ""
        return f"{self.jenkins_base_url}{job_path}"

    async def _process_jobs(
        self, jobs: list[dict[str, Any]], parent_job: Optional[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Process the list of jobs, optionally attaching information from the parent job.
        If a job has no builds, recursively fetch and include its child jobs.

        Args:
            jobs (list[dict]): List of jobs to process.
            parent_job (Optional[dict]): Parent job information to attach to each job.

        Returns:
            list[dict]: Processed list of jobs with optional parent job information.
        """
        job_batch = []

        for job in jobs:
            if parent_job:
                job["__parentJob"] = parent_job

            if "builds" not in job:
                async for child_jobs in self.fetch_jobs_and_builds_from_api(job):
                    job_batch.extend(child_jobs)
            else:
                job_batch.append(job)

        return job_batch

    async def get_single_resource(self, resource_url: str) -> dict[str, Any]:
        """
        Get either a job or build using the url from the event e.g.

        Job: job/JobName/
        Build: job/JobName/34/
        """
        response = await self.client.get(
            f"{self.jenkins_base_url}/{resource_url}api/json"
        )
        response.raise_for_status()
        return response.json()
