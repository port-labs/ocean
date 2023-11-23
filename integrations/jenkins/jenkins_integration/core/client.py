from datetime import datetime
from typing import Any, AsyncGenerator
from pydantic import HttpUrl
import httpx

from jenkins_integration.core.types.api_responses import (
    BuildAPIResponse,
    BuildListAPIResponse,
    JobAPIResponse,
    JobListAPIResponse,
)


class JenkinsClient:
    ...

    def __init__(self, username: str, password: str, host: HttpUrl) -> None:
        basic_auth = (username, password)
        self.client = httpx.AsyncClient(auth=basic_auth)
        self.host = host

    @staticmethod
    def _transform_jobs(jobs: list[JobAPIResponse]) -> list[dict[str, Any]]:
        return [
            {
                "name": job["name"],
                "status": job["lastBuild"]["result"],
                # Jenkins timestamps are in milliseconds
                "timestamp": datetime.utcfromtimestamp(
                    job["lastBuild"]["timestamp"] / 1000
                ).isoformat(),
                "url": job["url"],
            }
            for job in jobs
        ]

    @staticmethod
    def _transform_builds(builds: list[BuildAPIResponse]) -> list[dict[str, Any]]:
        return [
            {
                "id": build["id"],
                "name": build["fullDisplayName"],
                "status": build["result"],
                # Jenkins timestamps are in milliseconds
                "timestamp": datetime.utcfromtimestamp(
                    build["timestamp"] / 1000
                ).isoformat(),
                "url": build["url"],
                "duration": (f"{round(build['duration'] / 1000, 2)} seconds"),
            }
            for build in builds
        ]

    async def get_jobs(
        self, batch_size: int
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        endpoint = f"{self.host}/api/json"
        starting_job_count = 0
        ending_job_count = starting_job_count + batch_size

        jobs_found = True

        while jobs_found:
            query_params = {
                "tree": (
                    "jobs[name,url,lastBuild[timestamp,result]]"
                    f"{{{starting_job_count},{ending_job_count}}}"
                ),
            }
            response = await self.client.get(endpoint, params=query_params)
            response.raise_for_status()
            data: JobListAPIResponse = response.json()
            jobs = data["jobs"]

            if not jobs:
                jobs_found = False
                continue

            yield self._transform_jobs(jobs)

            if len(jobs) < batch_size:
                jobs_found = False
                continue

            starting_job_count = ending_job_count
            ending_job_count += batch_size

    async def get_builds(
        self, job_name: str, batch_size: int
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        endpoint = f"{self.host}/job/{job_name}/api/json"
        starting_build_count = 0
        ending_build_count = starting_build_count + batch_size
        builds_found = True

        while builds_found:
            query_params = {
                "tree": (
                    "builds[id,result,url,timestamp,duration,fullDisplayName]"
                    f"{{{starting_build_count},{ending_build_count}}}"
                ),
            }
            response = await self.client.get(endpoint, params=query_params)
            response.raise_for_status()
            data: BuildListAPIResponse = response.json()
            builds = data["builds"]

            if not builds:
                builds_found = False
                continue

            yield self._transform_builds(builds)

            if len(builds) < batch_size:
                builds_found = False
                continue

            starting_build_count = ending_build_count
            ending_build_count += batch_size
