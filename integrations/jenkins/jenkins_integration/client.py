from urllib.parse import urlencode, urlparse
import httpx
from typing import Any, AsyncGenerator
from loguru import logger
from jenkins_integration.utils import convert_timestamp_to_utc, url_encode


class JenkinsClient:
    def __init__(
        self, jenkins_base_url: str, jenkins_user: str, jenkins_password: str
    ) -> None:
        self.jenkins_base_url = jenkins_base_url
        auth = (jenkins_user, jenkins_password)
        self.client = httpx.AsyncClient(auth=auth)

    async def get_jobs(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        per_page = 100
        page = 0
        logger.info("Getting jobs from Jenkins")

        while True:
            # Parameters for pagination
            params = {"tree": "jobs[name,url,description,display_name,full_display_name,full_name]"}
            encoded_params = urlencode(params)

            job_response = await self.client.get(f"{self.jenkins_base_url}/api/json?{encoded_params}")
            job_response.raise_for_status()
            jobs = job_response.json()["jobs"]

            # If there are no more jobs, exit the loop
            if not jobs:
                break

            logger.info(f"Got {len(jobs)} jobs from Jenkins")

            transformed = [
                {
                    "type": "item.updated",
                    "data": job,
                    "url": urlparse(job.get("url")).path.lstrip("/"),  # Blueprint expects path rather than host
                    "fullUrl": job.get("url"),
                    "time": job.get("timestamp"),
                }
                for job in jobs
            ]

            yield transformed
            page += 1

            if len(jobs) < per_page:
                break

    async def get_builds(self, job_name: str) -> list[dict[str, Any]]:
        logger.info(f"Getting builds from Jenkins for job {job_name}")

        params = {"tree": "builds[id,number,url,result,duration,timestamp,display_name,full_display_name]"}
        encoded_params = urlencode(params)

        build_response = await self.client.get(f"{self.jenkins_base_url}/job/{job_name}/api/json?{encoded_params}")
        build_response.raise_for_status()
        builds = build_response.json().get("builds", [])
        logger.info(f"Got {len(builds)} builds from Jenkins for job {job_name}")

        transformed_builds = [
            {
                "type": "run.finalize",
                "source": url_encode(f"job/{job_name}/"),
                "url": build.get("url", None),
                "data": {
                    **build,
                    "timestamp": convert_timestamp_to_utc(build.get("timestamp")),
                },
            }
            for build in builds
        ]
        return transformed_builds