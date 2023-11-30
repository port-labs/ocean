from urllib.parse import urlencode, quote

import httpx
from typing import Any, AsyncGenerator

from loguru import logger


class JenkinsClient:
    def __init__(
        self, jenkins_base_url: str, jenkins_user: str, jenkins_password: str
    ) -> None:
        self.jenkins_base_url = jenkins_base_url

        auth = (jenkins_user, jenkins_password)
        self.client = httpx.AsyncClient(auth=auth)

    async def get_jobs(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        page_size = 100
        page = 0
        logger.info("Getting jobs from Jenkins")

        try:
            while True:
                start_idx = page_size * page
                end_idx = start_idx + page_size

                params = {
                    "tree": f"jobs[name,url,description,displayName,fullDisplayName,fullName]{{{start_idx},{end_idx}}}"
                }
                encoded_params = urlencode(params)
                logger.info(params)

                job_response = await self.client.get(
                    f"{self.jenkins_base_url}/api/json?{encoded_params}"
                )
                job_response.raise_for_status()
                jobs = job_response.json()["jobs"]

                if not jobs:
                    break

                logger.info(f"Got {len(jobs)} jobs from Jenkins")

                yield jobs
                page += 1

                if len(jobs) < page_size:
                    break
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching Jenkins data {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            raise

    async def get_builds(self, job_name: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        page_size = 100
        page = 0

        logger.info(f"Getting builds from Jenkins for job {job_name}")
        try:
            while True:
                start_idx = page_size * page
                end_idx = start_idx + page_size

                # Parameters for pagination
                params = {"tree": f"builds[id,number,url,result,duration,timestamp,displayName,fullDisplayName]{{{start_idx},{end_idx}}}"}
                encoded_params = urlencode(params)
                request_url = f"{self.jenkins_base_url}/job/{job_name}/api/json?{encoded_params}"

                build_response = await self.client.get(request_url)
                build_response.raise_for_status()
                builds = build_response.json().get("builds", [])

                # If there are no more builds, exit the loop
                if not builds:
                    break

                logger.info(f"Got {len(builds)} builds from Jenkins for job {job_name}")

                garnished_builds = [{**d, "source": quote(f"job/{job_name}/")} for d in builds]

                yield garnished_builds
                page += 1

                if len(garnished_builds) < page_size:
                    break

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching Jenkins data {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            raise
