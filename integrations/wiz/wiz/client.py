import csv
import json
import time
from enum import StrEnum
from typing import AsyncGenerator, Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr

from port_ocean.context.event import event
from port_ocean.exceptions.core import OceanAbortException
from port_ocean.utils import http_async_client
from port_ocean.utils.misc import get_time
from .constants import (
    GRAPH_QUERIES,
    ISSUES_GQL,
    AUTH0_URLS,
    COGNITO_URLS,
    PAGE_SIZE,
    MAX_PAGES,
    CREATE_REPORT_MUTATION,
    GET_REPORT,
    DOWNLOAD_REPORT_QUERY,
    MAX_RETRIES_FOR_DOWNLOAD_REPORT,
    CHECK_INTERVAL_FOR_DOWNLOAD_REPORT,
    RETRY_TIME_FOR_DOWNLOAD_REPORT,
    RERUN_REPORT_MUTATION,
    PORT_REPORT_NAME,
)


class CacheKeys(StrEnum):
    ISSUES = "wiz_issues"
    PROJECTS = "wiz_projects"


class InvalidTokenUrlException(OceanAbortException):
    def __init__(self, url: str, auth0_urls: list[str], cognito_urls: list[str]):
        base_message = f"The token url {url} is not valid."
        super().__init__(
            f"{base_message} Valid token urls for AuthO are {auth0_urls} and for Cognito: {cognito_urls}"
        )


class TokenResponse(BaseModel):
    access_token: str = Field(alias="access_token")
    expires_in: int = Field(alias="expires_in")
    token_type: str = Field(alias="token_type")
    _retrieved_time: int = PrivateAttr(get_time())

    @property
    def expired(self) -> bool:
        return self._retrieved_time + self.expires_in < get_time()

    @property
    def full_token(self) -> str:
        return f"{self.token_type} {self.access_token}"


class WizClient:
    def __init__(
        self, api_url: str, client_id: str, client_secret: str, token_url: str
    ):
        self.api_url = api_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.last_token_object: TokenResponse | None = None

        self.http_client = http_async_client

    @property
    def auth_request_params(self) -> dict[str, Any]:
        audience_mapping = {
            **{url: "beyond-api" for url in AUTH0_URLS},
            **{url: "wiz-api" for url in COGNITO_URLS},
        }

        if self.token_url not in audience_mapping:
            raise InvalidTokenUrlException(
                "Invalid Token URL specified", AUTH0_URLS, COGNITO_URLS
            )

        audience = audience_mapping[self.token_url]

        return {
            "grant_type": "client_credentials",
            "audience": audience,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

    async def _get_token(self) -> TokenResponse:
        logger.info(f"Fetching access token for Wiz clientId: {self.client_id}")

        response = await self.http_client.post(
            self.token_url,
            data=self.auth_request_params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return TokenResponse(**response.json())

    @property
    async def token(self) -> str:
        """
        Asynchronously retrieves and returns the access token for Wiz.
        """
        if not self.last_token_object or self.last_token_object.expired:
            logger.info("Wiz Token expired or is invalid, fetching new token")
            self.last_token_object = await self._get_token()

        return self.last_token_object.full_token

    @property
    async def auth_headers(self) -> dict[str, Any]:
        return {
            "Authorization": await self.token,
            "Content-Type": "application/json",
        }

    async def make_graphql_query(
        self, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            logger.info(f"Posting graphql query with variables {variables}")

            response = await self.http_client.post(
                url=self.api_url,
                json={"query": query, "variables": variables},
                headers=await self.auth_headers,
            )
            response.raise_for_status()
            response_json = response.json()

            return response_json["data"]
        except httpx.HTTPError as e:
            logger.error(f"Error while making GraphQL query: {str(e)}")
            raise

    async def _get_paginated_resources(
        self, resource: str, variables: dict[str, Any]
    ) -> AsyncGenerator[list[Any], None]:
        logger.info(f"Fetching {resource} data from Wiz API")
        page_num = 1

        while page_num <= MAX_PAGES:
            logger.info(f"Fetching page {page_num} of {MAX_PAGES}")
            gql = GRAPH_QUERIES[resource]
            data = await self.make_graphql_query(gql, variables)

            yield data[resource]["nodes"]

            cursor = data[resource].get("pageInfo") or {}
            if not cursor.get("hasNextPage", False):
                break  # Break out of the loop if no more pages

            # Set the cursor for the next page request
            variables["after"] = cursor.get("endCursor", "")
            page_num += 1

    async def get_issues(
        self, page_size: int = PAGE_SIZE
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(CacheKeys.ISSUES):
            logger.info("Picking Wiz issues from cache")
            yield cache
            return

        variables: dict[str, Any] = {
            "first": page_size,
            "orderBy": {"direction": "DESC", "field": "CREATED_AT"},
        }

        async for issues in self._get_paginated_resources(
            resource="issues", variables=variables
        ):
            event.attributes.setdefault(CacheKeys.ISSUES, []).extend(issues)
            yield issues

    async def get_projects(
        self, page_size: int = PAGE_SIZE
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(CacheKeys.PROJECTS):
            logger.info("Picking Wiz projects from cache")
            yield cache
            return

        variables: dict[str, Any] = {"first": page_size}

        async for projects in self._get_paginated_resources(
            resource="projects", variables=variables
        ):
            event.attributes.setdefault(CacheKeys.PROJECTS, []).extend(projects)
            yield projects

    async def get_single_issue(self, issue_id: str) -> dict[str, Any]:
        logger.info(f"Fetching issue with id {issue_id}")

        query_variables = {
            "first": 1,
            "filterBy": {"id": issue_id},
        }

        response_data = await self.make_graphql_query(ISSUES_GQL, query_variables)
        issue = response_data.get("issues", {}).get("nodes", [])[0]
        return issue

    async def setup_integration_report(self) -> None:
        logger.info(f"Creating report '{PORT_REPORT_NAME}' to fetch issues")

        report = await self.get_integration_report()
        if report:
            logger.info(f"Report already exists. Skipping creation: {report}")
            return

        logger.info("Report does not exist. Creating...")
        await self.create_report()

    async def create_report(self) -> str:
        report_project_id = "*"
        report_type = "DETAILED"
        report_issue_status = ["OPEN", "IN_PROGRESS"]

        report_variables = {
            "input": {
                "name": PORT_REPORT_NAME,
                "type": "ISSUES",
                "projectId": report_project_id,
                "issueParams": {
                    "type": report_type,
                    "issueFilters": {"status": report_issue_status},
                },
            }
        }

        response_data = await self.make_graphql_query(
            CREATE_REPORT_MUTATION, report_variables
        )
        logger.info(f"Report creation response: {response_data}")
        report_id = response_data["createReport"]["report"]["id"]
        logger.info(f"Created report with id {report_id}")
        return report_id

    async def get_integration_report(self) -> dict[str, Any]:
        logger.info("Checking the Port Integration Report Details")

        filters = {
            "first": 1,
            "filterBy": {
                "search": PORT_REPORT_NAME,
                "lastReportRunStatus": ["COMPLETED", "IN_PROGRESS"],
            },
        }

        response_data = await self.make_graphql_query(GET_REPORT, filters)
        reports = response_data.get("reports", {}).get("nodes", [])

        if reports:
            return reports[0]

        logger.info("Port integration report not found.")
        return {}

    async def rerun_report(self, report_id: str) -> str:
        logger.info(f"Restarting report {report_id} generation")

        filters = {"reportId": report_id}
        response = await self.make_graphql_query(RERUN_REPORT_MUTATION, filters)
        report_id = response["rerunReport"]["report"]["id"]
        logger.info("Report was re-run successfully. Report ID: %s", report_id)
        return report_id

    async def get_report_url_and_status(self, report_id: str) -> Any:
        logger.info("Getting the Port Integration Report Download URL")

        filters = {"reportId": report_id}
        num_of_retries = 0

        while num_of_retries < MAX_RETRIES_FOR_DOWNLOAD_REPORT:
            logger.info(
                f"Report is still creating, waiting {CHECK_INTERVAL_FOR_DOWNLOAD_REPORT} seconds"
            )

            time.sleep(CHECK_INTERVAL_FOR_DOWNLOAD_REPORT)
            response = await self.make_graphql_query(DOWNLOAD_REPORT_QUERY, filters)
            status = response["report"]["lastRun"]["status"]

            if status == "COMPLETED":
                return response["report"]["lastRun"]["url"]
            elif status == "FAILED" or status == "EXPIRED":
                logger.info(
                    f"Report failed or expired, re-running the report and waiting {RETRY_TIME_FOR_DOWNLOAD_REPORT}",
                )
                await self.rerun_report(report_id)
                time.sleep(RETRY_TIME_FOR_DOWNLOAD_REPORT)
                num_of_retries += 1

        raise Exception("Download failed, exceeding the maximum number of retries")

    async def get_reported_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        report = await self.get_integration_report()
        report_url = await self.get_report_url_and_status(report["id"])

        logger.info(f"Dowloading the Port Integration Report: {report['name']}")
        async for chunk in self.stream_and_parse_csv(report_url, 50, 2):
            yield chunk

    async def stream_and_parse_csv(
        self, download_url: str, chunk_size: int = PAGE_SIZE, max_pages: int = MAX_PAGES
    ) -> AsyncGenerator[list[dict[str, str]], None]:
        start_time = time.time()
        total_records = 0
        chunk_count = 0
        current_page = 0

        logger.info("Starting CSV download and processing")

        try:
            with httpx.stream("GET", download_url) as r:
                r.raise_for_status()  # Ensure successful download
                reader = csv.reader(r.iter_lines())

                headers = next(reader, None)  # Get the header row
                if not headers:
                    logger.error("CSV appears to be empty or without headers")
                    return

                chunk: list[dict[str, str]] = []

                for row in reader:
                    if len(row) != len(headers):
                        logger.warning(f"Row length mismatch. Skipping: {row}")
                        continue

                    transformed_headers = list(
                        map(lambda x: x.lower().replace(" ", "_"), headers)
                    )

                    obj = {transformed_headers[i]: row[i] for i in range(len(headers))}
                    obj["resource_tags"] = json.loads(obj["resource_tags"])
                    chunk.append(obj)

                    total_records += 1

                    if len(chunk) == chunk_size:
                        yield chunk
                        chunk = []
                        chunk_count += 1
                        current_page += 1

                        if max_pages and current_page >= max_pages:
                            break

                if chunk:
                    yield chunk
                    chunk_count += 1

        except requests.RequestException as exc:
            logger.exception(f"Requests error occurred: {exc}")
            raise

        except Exception as exc:
            logger.exception(f"Error occured when processing Issues report: {exc}")
            raise

        end_time = time.time()
        duration = end_time - start_time
        logger.info(
            f"CSV processing finished. Processed {total_records} records in {chunk_count} chunks (max_pages: {max_pages}). Duration: {duration:.2f} seconds"
        )
