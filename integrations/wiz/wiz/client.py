import asyncio
import functools
from enum import StrEnum
from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger
from port_ocean.context.event import event
from port_ocean.exceptions.core import OceanAbortException
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from port_ocean.utils import http_async_client
from port_ocean.utils.misc import get_time
from pydantic import BaseModel, Field, PrivateAttr
from wiz.options import (
    IssueOptions,
    ProjectOptions,
    SbomArtifactOptions,
    VulnerabilityFindingOptions,
)

from .constants import (
    AUTH0_URLS,
    COGNITO_URLS,
    GRAPH_QUERIES,
    ISSUES_GQL,
    PAGE_SIZE,
    MAX_SBOM_ARTIFACT_ENTITIES,
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
    _MAX_CONCURRENT_SBOM_GROUP_FETCHES = 10  # Wiz has 10 concurrent requests limit per service account according to https://docs.stellarcyber.ai/6.3.x/Configure/Connectors/Wiz-Connectors.htm

    _SBOM_TYPE_FILTER_KEYS = (
        "codeLibraryLanguage",
        "osPackageManager",
        "plugin",
        "custom",
        "ciComponent",
    )

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
            graphql_errors = response_json.get("errors") or []
            data = response_json.get("data")

            if graphql_errors:
                raise OceanAbortException(
                    f"Wiz GraphQL returned errors for query variables {variables}: {graphql_errors}"
                )

            if data is None:
                logger.warning(
                    f"Wiz GraphQL returned null data for query variables {variables}. Response: {response_json}"
                )

            return data
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
            resource_data = data.get(resource)
            if not isinstance(resource_data, dict):
                raise OceanAbortException(
                    f"Wiz GraphQL response is missing '{resource}' object. Available keys: {list(data.keys())}"
                )

            nodes = resource_data.get("nodes")
            if not isinstance(nodes, list):
                raise OceanAbortException(
                    f"Wiz GraphQL response for '{resource}' includes invalid 'nodes'"
                )

            yield nodes

            cursor = resource_data.get("pageInfo") or {}
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
    ) -> dict[str, Any] | None:
        logger.info(f"Fetching issue with id {issue_id}")

        query_variables = {
            "first": 1,
            "filterBy": {"id": issue_id},
        }

        query_variables.update(
            self._enrich_variables_with_issue_options(query_variables, options)
        )
        response_data = await self.make_graphql_query(ISSUES_GQL, query_variables)
        nodes = response_data.get("issues", {}).get("nodes", [])
        if not nodes:
            return None
        return nodes[0]

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

    async def get_vulnerability_findings(
        self,
        options: VulnerabilityFindingOptions,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        variables: dict[str, Any] = {
            "first": page_size,
            "filterBy": {},
        }

        if options.get("status_list"):
            variables["filterBy"]["status"] = options["status_list"]

        if options.get("severity_list"):
            variables["filterBy"]["severity"] = options["severity_list"]

        async for findings in self._get_paginated_resources(
            resource="vulnerabilityFindings",
            variables=variables,
            max_pages=options.get("max_pages"),
        ):
            yield findings

    async def get_technologies(
        self,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        variables: dict[str, Any] = {
            "first": page_size,
            "filterBy": {},
        }

        async for technologies in self._get_paginated_resources(
            resource="technologies",
            variables=variables,
        ):
            yield technologies

    async def get_hosted_technologies(
        self,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        variables: dict[str, Any] = {
            "first": page_size,
            "filterBy": {},
        }

        async for hosted in self._get_paginated_resources(
            resource="hostedTechnologies",
            variables=variables,
        ):
            yield hosted

    async def get_repositories(
        self,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        variables: dict[str, Any] = {
            "first": page_size,
            "filterBy": {},
        }

        async for repos in self._get_paginated_resources(
            resource="repositories",
            variables=variables,
        ):
            yield repos

    def _build_sbom_artifact_type_filter(
        self, sbom_type: dict[str, Any] | None
    ) -> dict[str, list[str]] | None:
        """
        Build a valid SBOMArtifactFilters.type object.
        Wiz expects exactly one type key with a list value.
        """
        if not isinstance(sbom_type, dict):
            return None

        for key in self._SBOM_TYPE_FILTER_KEYS:
            raw_value = sbom_type.get(key)
            if isinstance(raw_value, str) and raw_value:
                return {key: [raw_value]}

        return None

    async def _get_sbom_artifacts_for_grouped_name(
        self,
        grouped_node: dict[str, Any],
        page_size: int,
        max_pages: int,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        name = grouped_node.get("name")
        sbom_type = grouped_node.get("type")

        if not isinstance(name, str) or not name:
            logger.warning(f"Skipping invalid SBOM grouped node name: {name}")
            return

        type_filter = self._build_sbom_artifact_type_filter(sbom_type)
        if not type_filter:
            logger.warning(
                f"Skipping SBOM grouped node '{name}' because no valid type filter was found"
            )
            return

        variables: dict[str, Any] = {
            "first": page_size,
            "filterBy": {
                "name": name,
                "type": type_filter,
            },
        }

        async for artifacts in self._get_paginated_resources(
            resource="sbomArtifacts",
            variables=variables,
            max_pages=max_pages,
        ):
            enriched_artifacts = []
            for artifact in artifacts:
                artifact["__groupTypeMetadata"] = grouped_node.get("type")
                enriched_artifacts.append(artifact)

            if enriched_artifacts:
                yield enriched_artifacts

    async def get_sbom_artifacts(
        self,
        options: SbomArtifactOptions,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        max_pages = min(options.get("max_pages", 500), 500)
        selected_groups = set(options.get("group_list") or [])
        allow_all_groups = not selected_groups
        total_ingested = 0

        logger.info(
            f"Resyncing SBOM artifacts with groups: {selected_groups or 'ALL'}, max pages: {max_pages} max artifacts: {MAX_SBOM_ARTIFACT_ENTITIES}"
        )

        grouped_variables: dict[str, Any] = {
            "first": page_size,
        }
        sbom_group_semaphore = asyncio.BoundedSemaphore(
            self._MAX_CONCURRENT_SBOM_GROUP_FETCHES
        )

        async for grouped_nodes in self._get_paginated_resources(
            resource="sbomArtifactsGroupedByName",
            variables=grouped_variables,
            max_pages=max_pages,
        ):
            if total_ingested >= MAX_SBOM_ARTIFACT_ENTITIES:
                logger.warning(
                    f"Reached maximum SBOM artifact limit of {MAX_SBOM_ARTIFACT_ENTITIES}. "
                    f"Stopping ingestion."
                )
                return

            grouped_artifact_streams = [
                semaphore_async_iterator(
                    sbom_group_semaphore,
                    functools.partial(
                        self._get_sbom_artifacts_for_grouped_name,
                        grouped_node=grouped_node,
                        page_size=page_size,
                        max_pages=max_pages,
                    ),
                )
                for grouped_node in grouped_nodes
                if allow_all_groups
                or ((grouped_node.get("type") or {}).get("group") in selected_groups)
            ]

            if not grouped_artifact_streams:
                continue

            async for artifact_batch in stream_async_iterators_tasks(
                *grouped_artifact_streams
            ):
                remaining = MAX_SBOM_ARTIFACT_ENTITIES - total_ingested

                if remaining <= 0:
                    logger.warning(
                        f"Reached maximum SBOM artifact limit of {MAX_SBOM_ARTIFACT_ENTITIES}. "
                        f"Stopping ingestion."
                    )
                    return
                # Trim the batch if it would exceed the limit
                if len(artifact_batch) > remaining:
                    artifact_batch = artifact_batch[:remaining]

                total_ingested += len(artifact_batch)
                yield artifact_batch
