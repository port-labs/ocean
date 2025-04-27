from enum import StrEnum
from typing import Any, AsyncGenerator, Optional, TypeVar, Callable
from urllib.parse import urlparse, urljoin
import httpx

from loguru import logger

from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean


PAGE_SIZE = 50

T = TypeVar("T")


class ResourceKey(StrEnum):
    JOBS = "jobs"
    BUILDS = "builds"
    STAGES = "stages"
    USERS = "users"


class JenkinsClient:
    def __init__(
        self, jenkins_base_url: str, jenkins_user: str, jenkins_token: str
    ) -> None:
        self.jenkins_base_url = jenkins_base_url
        self.client = http_async_client
        self.client.auth = httpx.BasicAuth(jenkins_user, jenkins_token)

    @classmethod
    def create_from_ocean_configuration(cls) -> "JenkinsClient":
        logger.info(f"Initializing JenkinsClient {ocean.integration_config}")
        return cls(
            ocean.integration_config["jenkins_host"],
            ocean.integration_config["jenkins_user"],
            ocean.integration_config["jenkins_token"],
        )

    async def _send_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Common method for making API requests to Jenkins.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (will be joined with base URL)
            params: Query parameters
            json: JSON body for POST requests
        """
        url = urljoin(self.jenkins_base_url, endpoint)
        logger.debug(f"Making {method} request to {url} with params {params}")

        try:
            response = await self.client.request(
                method=method, url=url, params=params, json=json
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to make request to {url}: {str(e)}")
            raise

    async def _paginate(
        self,
        endpoint: str,
        extract_items: Callable[[dict[str, Any]], list[T]],
        params_builder: Callable[[int, int], dict[str, Any]],
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[T], None]:
        """
        Generic pagination method.

        Args:
            endpoint: API endpoint
            extract_items: Function to extract items from response
            params_builder: Function to build pagination parameters
            page_size: Number of items per page
        """
        page = 0

        while True:
            start_idx = page_size * page
            end_idx = start_idx + page_size

            params = params_builder(start_idx, end_idx)

            response_data = await self._send_api_request("GET", endpoint, params=params)
            items = extract_items(response_data)

            if not items:
                break

            yield items

            if len(items) < page_size:
                break

            page += 1

    async def get_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get users with pagination support for both old and new endpoints."""
        if cache := event.attributes.get(ResourceKey.USERS):
            logger.info("picking jenkins users from cache")
            yield cache
            return

        url = "people/api/json"

        async for users in self._paginate(
            url,
            lambda response: response.get("users", []),
            lambda start, end: {"tree": f"users[user[*],*]{{{start},{end}}}"},
        ):
            event.attributes.setdefault(ResourceKey.USERS, []).extend(users)
            yield users

    async def get_jobs(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(ResourceKey.JOBS):
            logger.info("picking jenkins jobs from cache")
            yield cache
            return

        def extract_jobs(response: dict[str, Any]) -> list[dict[str, Any]]:
            return response.get("jobs", [])

        def build_params(start: int, end: int) -> dict[str, Any]:
            return self._build_api_params(
                ResourceKey.JOBS, end - start, start // PAGE_SIZE
            )

        async for jobs in self._paginate("api/json", extract_jobs, build_params):
            event.attributes.setdefault(ResourceKey.JOBS, []).extend(jobs)
            yield jobs

    async def get_builds(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(ResourceKey.BUILDS):
            logger.info("picking jenkins builds from cache")
            yield cache
            return

        async for _jobs in self.fetch_resources(ResourceKey.BUILDS):
            builds = [build for job in _jobs for build in job.get("builds", [])]
            logger.debug(f"Builds received {builds}")
            event.attributes.setdefault(ResourceKey.BUILDS, []).extend(builds)
            yield builds

    async def _get_build_stages(self, build_url: str) -> list[dict[str, Any]]:
        response = await self._send_api_request("GET", f"{build_url}/wfapi/describe")
        stages = response.get("stages", [])
        return stages

    async def _get_job_builds(self, job_url: str) -> AsyncGenerator[Any, None]:
        job_details = await self.get_single_resource(job_url)
        if job_details.get("buildable"):
            yield job_details.get("builds")

        job = {"url": job_url}
        async for _jobs in self.fetch_resources(ResourceKey.BUILDS, job):
            builds = [build for job in _jobs for build in job.get("builds", [])]
            yield builds

    async def get_stages(
        self, job_url: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for builds in self._get_job_builds(job_url):
            stages: list[dict[str, Any]] = []
            for build in builds:
                build_url = build["url"]
                try:
                    logger.info(f"Getting stages for build {build_url}")
                    build_stages = await self._get_build_stages(build_url)
                    stages.extend(build_stages)
                    yield build_stages
                except Exception as e:
                    logger.error(
                        f"Failed to get stages for build {build_url}: {e.args[0]}"
                    )

    async def fetch_resources(
        self, resource: str, parent_job: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:

        base_url = self._build_base_url(parent_job)

        async for jobs in self._paginate(
            endpoint=f"{base_url}/api/json",
            extract_items=lambda response: response.get("jobs", []),
            params_builder=lambda start, end: self._build_api_params(
                resource, end - start, start // PAGE_SIZE
            ),
        ):
            logger.info(f"Fetching {resource} from {base_url}")
            logger.info(f"Fetched jobs: {jobs} of length {len(jobs)}")

            enriched_jobs = self.enrich_jobs(jobs, parent_job)
            yield [job for job in enriched_jobs if job.get("buildable")]

            folder_jobs = [job for job in enriched_jobs if job.get("jobs")]
            for job in folder_jobs:
                async for fetched_jobs in self.fetch_resources(resource, job):
                    yield fetched_jobs

    def _build_api_params(
        self, resource: str, page_size: int, page: int
    ) -> dict[str, Any]:
        start_idx = page_size * page
        end_idx = start_idx + page_size

        jobs_pagination = f"{{{start_idx},{end_idx}}}"
        builds_query = (
            ",builds[id,number,url,result,duration,timestamp,displayName,fullDisplayName,previousBuild[id,url]]{0,100}"
            if resource == "builds"
            else ""
        )
        jobs_query = f"jobs[name,url,displayName,fullName,color,buildable,jobs[name,color,fullName,displayName,url]{builds_query}]"

        return {"tree": jobs_query + jobs_pagination}

    def _build_base_url(self, parent_job: Optional[dict[str, Any]]) -> str:
        job_path = urlparse(parent_job["url"]).path if parent_job else ""
        return f"{self.jenkins_base_url}{job_path}"

    def enrich_jobs(
        self, jobs: list[dict[str, Any]], parent_job: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        if parent_job:
            return [{**job, "__parentJob": parent_job} for job in jobs]

        return jobs

    async def get_single_resource(self, resource_url: str) -> dict[str, Any]:
        """
        Get either a job or build using the url from the event e.g.

        Job: job/JobName/
        Build: job/JobName/34/
        """
        # Ensure resource_url ends with a slash
        if not resource_url.endswith("/"):
            resource_url += "/"

        # Construct the full URL using urljoin
        fetch_url = urljoin(self.jenkins_base_url, f"{resource_url}api/json")

        return await self._send_api_request("GET", fetch_url)
