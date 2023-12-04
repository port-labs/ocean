from loguru import logger
import httpx
from urllib.parse import urljoin

import urllib

from typing import AsyncGenerator
class JenkinsClient:

    def __init__(self, base_url: str, username: str, token: str):
        self.base_url = base_url.rstrip('/')
        auth = (username, token)
        self.client = httpx.AsyncClient(auth=auth)

    async def get_paginated_jobs(self,start:int = 0,limit:int = 50) -> AsyncGenerator[list[dict], None]:
        """
            Initialize the JenkinsClient.

            Args:
                base_url (str): The base URL of the Jenkins server.
                username (str): The username for Jenkins authentication.
                token (str): The API token for Jenkins authentication.

            Attributes:
                base_url (str): The base URL of the Jenkins server.
                client (httpx.AsyncClient): An asynchronous HTTP client for making requests.
        """
                
        current_start = start   

        while True:

            jobs_url = urljoin(self.base_url, f"api/json?tree=jobs[name,url,color,buildable,description,fullName]{{{current_start},{limit}}}")
            response = await self.client.get(jobs_url)
            response.raise_for_status()
            paginated_jobs = response.json().get('jobs', [])

            logger.info(f"Fetched {len(paginated_jobs)} jobs from Jenkins")

            yield paginated_jobs

            if len(paginated_jobs) < limit:
                break

            current_start += limit


    async def get_paginated_builds(self, job_url: str,start = 0,limit = 50) -> AsyncGenerator[list[dict], None]:
        """
            Asynchronously fetches builds for a specific Jenkins job in a paginated manner.
            Args:
                job_url (str): The URL of the Jenkins job for which builds are to be fetched.
            Yields:
                AsyncGenerator[list[dict], None]: A generator that yields lists of builds, each list representing a page of builds for the specified job.
            Raises:
                HTTPError: If the request to the Jenkins API fails.
        """

        current_start = start 
        
        while True:

            builds_url = urljoin(job_url, f"api/json?tree=builds[number,url,result]{{{current_start},{limit}}}")
            response = await self.client.get(builds_url)
            response.raise_for_status()

            paginated_builds = response.json().get('builds', [])

            logger.info(f"Fetched {len(paginated_builds)} builds from Jenkins")

            build_details_list = []

            for build in paginated_builds:
                build_details_url = urljoin(build['url'], "api/json")
                build_details_response = await self.client.get(build_details_url)
                build_details_response.raise_for_status()
                build_details = build_details_response.json()
                build_details_list.append(build_details)

            yield build_details_list           

            if len(paginated_builds) < limit:
                break

            current_start += limit


    async def close(self):
        """Closes the asynchronous HTTP client session."""
        await self.client.aclose()