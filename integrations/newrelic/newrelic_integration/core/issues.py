from enum import Enum
from typing import Optional

from port_ocean.context.ocean import ocean

from newrelic_integration.utils import (
    get_port_resource_configuration_by_newrelic_entity_type,
)
from newrelic_integration.core.paging import send_paginated_graph_api_request
from newrelic_integration.core.entities import EntitiesHandler


class IssueState(Enum):
    ACTIVATED = "ACTIVATED"
    CLOSED = "CLOSED"
    CREATED = "CREATED"
    DEACTIVATED = "DEACTIVATED"


class IssuesHandler:
    async def get_number_of_issues_by_entity_guid(
        self, entity_guid: str, issue_state: IssueState = IssueState.ACTIVATED
    ):
        # specifying the minimal fields to reduce the response size
        query_template = """
{
  actor {
    account(id: {{ account_id }}) {
      aiIssues {
        issues(filter: {entityGuids: "{{ entity_guid }}"}{{ next_cursor_request }}) {
          issues {
            entityGuids
            issueId
            state
            closedAt
          }
          nextCursor
        }
      }
    }
  }
}
        """
        counter = 0
        async for issue in send_paginated_graph_api_request(
            query_template,
            extract_data=self._extract_issues,
            account_id=ocean.integration_config.get("new_relic_account_id"),
            entity_guid=entity_guid,
        ):
            if issue["state"] == issue_state.value:
                counter += 1
        return counter

    async def list_issues(self, state: IssueState = None):
        # TODO: filter by state once the API supports it
        # https://forum.newrelic.com/s/hubtopic/aAX8W00000005U2WAI/nerdgraph-api-issues-query-state-filter-does-not-seem-to-be-working
        query_template = """
{
  actor {
    account(id: {{ account_id }}) {
      aiIssues {
        issues{{ next_cursor_request }} {
          issues {
            issueId
            priority
            state
            title
            conditionName
            description
            entityGuids
            policyName
            createdAt
            origins
            policyIds
            sources
            activatedAt
          }
          nextCursor
        }
      }
    }
  }
}
"""
        matching_issues = []
        async for issue in send_paginated_graph_api_request(
            query_template,
            extract_data=self._extract_issues,
            account_id=ocean.integration_config.get("new_relic_account_id"),
        ):
            if state is None or issue["state"] == state.value:
                for entity_guid in issue["entityGuids"]:
                    # for each related entity we need to get the entity type and then find the corresponding
                    # resource configuration to get the relation identifier so that we will be able to map the
                    # relevant entity id to correct relation identifier
                    entity = await EntitiesHandler().get_entity(entity_guid)
                    resource_configuration = (
                        await get_port_resource_configuration_by_newrelic_entity_type(
                            entity["type"]
                        )
                    )
                    issue.setdefault(
                        resource_configuration.get("selector", {}).get(
                            "relation_identifier"
                        ),
                        {},
                    ).setdefault("entity_guids", []).append(entity_guid)

                matching_issues.append(issue)
        return matching_issues

    @staticmethod
    async def _extract_issues(response: dict) -> (Optional[str], list[Optional[dict]]):
        """Extract issues from the response. used by send_paginated_graph_api_request"""
        results = (
            response.get("data", {})
            .get("actor", {})
            .get("account", {})
            .get("aiIssues", {})
            .get("issues", {})
        )
        return results.get("nextCursor"), results.get("issues", [])
