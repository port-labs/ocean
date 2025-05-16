from enum import Enum
from typing import List, Optional, Any, Tuple
from loguru import logger

import httpx

from port_ocean.context.ocean import ocean
from pydantic import BaseModel, Field, Extra

from newrelic_integration.core.errors import NewRelicNotFoundError
from newrelic_integration.core.entities import EntitiesHandler
from newrelic_integration.core.query_templates.issues import (
    LIST_ISSUES_BY_ENTITY_GUIDS_MINIMAL_QUERY,
    LIST_ISSUES_QUERY,
    GET_ISSUE_ENTITY_GUIDS_QUERY,
)
from newrelic_integration.core.paging import send_paginated_graph_api_request
from newrelic_integration.utils import render_query
from newrelic_integration.core.utils import send_graph_api_request


class IssueEvent(BaseModel, extra=Extra.allow):
    id: str = Field(..., alias="id")
    title: str
    state: str
    entity_guids: Optional[list[str]] = Field(default=None, alias="entityGuids")


class IssueState(Enum):
    ACTIVATED = "ACTIVATED"
    CLOSED = "CLOSED"
    CREATED = "CREATED"
    DEACTIVATED = "DEACTIVATED"


class IssuesHandler:
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def get_number_of_issues_by_entity_guid(
        self,
        entity_guid: str,
        issue_state: IssueState = IssueState.ACTIVATED,
    ) -> int:
        counter = 0
        async for issue in send_paginated_graph_api_request(
            self.http_client,
            LIST_ISSUES_BY_ENTITY_GUIDS_MINIMAL_QUERY,
            request_type="get_number_of_issues_by_entity_guid",
            extract_data=self._extract_issues,
            account_id=ocean.integration_config.get("new_relic_account_id"),
            entity_guid=entity_guid,
        ):
            if issue["state"] == issue_state.value:
                counter += 1
        return counter

    async def list_issues(
        self, state: IssueState | None = None
    ) -> list[dict[Any, Any]]:
        matching_issues = []
        # key is entity guid and value is the entity type
        # used for caching the entity type for each entity guid and avoid querying it multiple times for
        # the same entity guid for different issues
        queried_entities: dict[str, str] = {}
        async for issue in send_paginated_graph_api_request(
            self.http_client,
            LIST_ISSUES_QUERY,
            request_type="list_issues",
            extract_data=self._extract_issues,
            account_id=ocean.integration_config.get("new_relic_account_id"),
        ):
            # clear the cache if it gets too big
            if len(queried_entities) > 1000:
                logger.debug("Clearing queried entities cache")
                queried_entities.clear()

            if state is None or issue["state"] == state.value:
                # for each related entity we need to get the entity type, so we can add it to the issue
                # related entities under the right relation key
                for entity_guid in issue["entityGuids"]:
                    try:
                        # if we already queried this entity guid before, we can use the cached relation identifier
                        if entity_guid not in queried_entities.keys():
                            entity = await EntitiesHandler(self.http_client).get_entity(
                                entity_guid
                            )
                            queried_entities[entity_guid] = entity["type"]

                        # add the entity guid to the right relation key in the issue
                        # by the format of .__<type>.entity_guids.[<entity_guid>...]
                        issue.setdefault(
                            f"__{queried_entities[entity_guid]}",
                            {},
                        ).setdefault("entity_guids", []).append(entity_guid)
                    except NewRelicNotFoundError:
                        logger.info(
                            f"Related entity guid {entity_guid} not found in new relic for issue {issue.get('issueId')}, continuing",
                        )
                    except Exception as err:
                        logger.exception(
                            f"Failed to get entity {entity_guid} for issue event {issue.get('issueId')}, continuing",
                            entity_guid=entity_guid,
                            err=str(err),
                        )

                matching_issues.append(issue)
        return matching_issues

    async def get_issue_entity_guids(self, issue_id: str) -> Optional[List[str]]:
        """Fetch and return the entityGuids for a given issue ID."""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        query = await render_query(
            GET_ISSUE_ENTITY_GUIDS_QUERY, account_id=account_id, issue_id=issue_id
        )

        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="get_issue_entity_guids",
            account_id=account_id,
            issue_id=issue_id,
        )
        issues_data = response["data"]["actor"]["account"]["aiIssues"]["issues"][
            "issues"
        ]

        if issues_data and len(issues_data) > 0:
            return issues_data[0].get("entityGuids")
        return None

    @staticmethod
    async def _extract_issues(
        response: dict[Any, Any]
    ) -> Tuple[Optional[str], list[dict[Any, Any]]]:
        """Extract issues from the response. used by send_paginated_graph_api_request"""
        results = (
            response.get("data", {})
            .get("actor", {})
            .get("account", {})
            .get("aiIssues", {})
            .get("issues", {})
        )
        return results.get("nextCursor"), results.get("issues", [])
