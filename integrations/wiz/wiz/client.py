from enum import StrEnum
from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger
from port_ocean.context.event import event
from port_ocean.exceptions.core import OceanAbortException
from port_ocean.utils import http_async_client
from port_ocean.utils.misc import get_time
from pydantic import BaseModel, Field, PrivateAttr
from wiz.options import IssueOptions, ProjectOptions

from .constants import (
    AUTH0_URLS,
    COGNITO_URLS,
    GRAPH_QUERIES,
    ISSUES_GQL,
    PAGE_SIZE,
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
            logger.info(f"Fetching graphql query with variables {variables}")

            response = await self.http_client.post(
                url=self.api_url,
                json={"query": query, "variables": variables},
                headers=await self.auth_headers,
                extensions={"retryable": True},
            )
            response.raise_for_status()
            response_json = response.json()

            return response_json["data"]
        except httpx.HTTPError as e:
            logger.error(f"Error while making GraphQL query: {str(e)}")
            raise

    async def _get_paginated_resources(
        self, resource: str, variables: dict[str, Any], max_pages: Optional[int] = None
    ) -> AsyncGenerator[list[Any], None]:
        logger.info(f"Fetching {resource} data from Wiz API")
        page_num = 1

        while True:
            logger.info(
                f"Fetching page {page_num} {f"of {max_pages}" if max_pages else ''}"
            )
            gql = GRAPH_QUERIES[resource]
            data = await self.make_graphql_query(gql, variables)

            yield data[resource]["nodes"]

            cursor = data[resource].get("pageInfo") or {}
            if not cursor.get("hasNextPage", False):
                break  # Break out of the loop if no more pages

            # Set the cursor for the next page request
            variables["after"] = cursor.get("endCursor", "")
            page_num += 1
            if max_pages and page_num >= max_pages:
                break

    async def get_issues(
        self,
        options: IssueOptions,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        variables: dict[str, Any] = {
            "first": page_size,
            "orderBy": {"direction": "DESC", "field": "CREATED_AT"},
        }
        variables.update(self._enrich_variables_with_issue_options(variables, options))

        async for issues in self._get_paginated_resources(
            resource="issues", variables=variables, max_pages=options["max_pages"]
        ):
            yield issues

    async def get_projects(
        self,
        options: ProjectOptions,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if cache := event.attributes.get(CacheKeys.PROJECTS):
            logger.info("Picking Wiz projects from cache")
            yield cache
            return

        variables: dict[str, Any] = {
            "first": page_size,
            "filterBy": {},
        }

        if options["include_archived"]:
            variables["filterBy"]["includeArchived"] = options["include_archived"]

        if options["impact"]:
            variables["filterBy"]["impact"] = options["impact"]

        async for projects in self._get_paginated_resources(
            resource="projects", variables=variables
        ):
            event.attributes.setdefault(CacheKeys.PROJECTS, []).extend(projects)
            yield projects

    async def get_single_issue(
        self, issue_id: str, options: IssueOptions
    ) -> dict[str, Any]:
        logger.info(f"Fetching issue with id {issue_id}")

        query_variables = {
            "first": 1,
            "filterBy": {"id": issue_id},
        }

        query_variables.update(
            self._enrich_variables_with_issue_options(query_variables, options)
        )
        response_data = await self.make_graphql_query(ISSUES_GQL, query_variables)
        issue = response_data.get("issues", {}).get("nodes", [])[0]
        return issue

    def _enrich_variables_with_issue_options(
        self, variables: dict[str, Any], options: IssueOptions
    ) -> dict[str, Any]:
        if "filterBy" not in variables:
            variables["filterBy"] = {}

        variables["filterBy"]["status"] = options["status_list"]

        if options["severity_list"]:
            variables["filterBy"]["severity"] = options["severity_list"]

        if options["type_list"]:
            variables["filterBy"]["type"] = options["type_list"]

        return variables
