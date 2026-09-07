from typing import Any

from linear.client.constants import LinearObject
from linear.client.graphql import GraphqlClient
from linear.helpers.exceptions import LinearActionError
from linear.mutations import queries
from linear.queries import QUERIES


class IssueMutations:
    def __init__(self, graphql: GraphqlClient) -> None:
        self._graphql = graphql

    async def get_single_issue(self, issue_identifier: str) -> dict[str, Any]:
        data = await self._graphql.execute_query_template(
            "GET_SINGLE_ISSUE",
            issue_identifier=issue_identifier,
            base_query_fields=QUERIES[f"BASE_{LinearObject.ISSUES}_QUERY_FIELDS"],
        )
        return data["issue"]

    async def create_issue(self, issue_input: dict[str, Any]) -> dict[str, Any]:
        result = await self._graphql.execute_mutation(
            queries.ISSUE_CREATE,
            {"input": issue_input},
            result_key="issueCreate",
        )
        issue = result.get("issue")
        if not isinstance(issue, dict) or not issue.get("id"):
            raise LinearActionError(
                "Linear returned an empty or incomplete issue create response"
            )
        return issue

    async def update_issue(
        self, issue_id: str, issue_input: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self._graphql.execute_mutation(
            queries.ISSUE_UPDATE,
            {"id": issue_id, "input": issue_input},
            result_key="issueUpdate",
        )
        issue = result.get("issue")
        if not isinstance(issue, dict) or not issue.get("id"):
            raise LinearActionError(
                "Linear returned an empty or incomplete issue update response"
            )
        return issue
