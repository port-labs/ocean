from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from pydantic import HttpUrl


class JenkinsClient:
    ...

    def __init__(self, username: str, password: str, host: HttpUrl) -> None:
        basic_auth = (username, password)
        self.client = httpx.AsyncClient(auth=basic_auth)
        self.host = host

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
            try:
                response = await self.client.get(endpoint, params=query_params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error("Error occurred while fetching jobs")
                logger.error(f"Error: {e.response.status_code}: {e.response.text}")
                jobs_found = False
                continue
            data: dict[str, Any] = response.json()
            jobs: list[dict[str, Any]] = data["jobs"]

            if not jobs:
                jobs_found = False
                continue

            yield jobs

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
            try:
                response = await self.client.get(endpoint, params=query_params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error("Error occurred while fetching builds")
                logger.error(f"Error: {e.response.status_code}: {e.response.text}")
                builds_found = False
                continue

            data: dict[str, Any] = response.json()
            builds: list[dict[str, Any]] = data["builds"]

            if not builds:
                builds_found = False
                continue

            yield builds

            if len(builds) < batch_size:
                builds_found = False
                continue

            starting_build_count = ending_build_count
            ending_build_count += batch_size
