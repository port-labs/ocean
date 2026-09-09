from typing import Any

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations import queries
from linear.helpers.exceptions import LinearActionError


class IssueMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_issue(self, issue_input: dict[str, Any]) -> dict[str, Any]:
        result = await self.graphql.execute_mutation(
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
        result = await self.graphql.execute_mutation(
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
