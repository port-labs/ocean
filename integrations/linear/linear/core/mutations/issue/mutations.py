from pydantic import ValidationError

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations.issue import queries
from linear.core.mutations.issue.types import (
    CommentCreateMutationPayload,
    IssueCreateMutationPayload,
    IssueUpdateMutationPayload,
    MutationComment,
    MutationCommentResult,
    MutationIssue,
    MutationIssueResult,
    ResolveStateByNameData,
)
from linear.helpers.exceptions import (
    CreateIssueError,
    LinearActionError,
    UpdateIssueError,
)
from port_ocean.utils.cache import cache_coroutine_result


class IssueMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_issue(self, payload: IssueCreateMutationPayload) -> MutationIssue:
        result = await self.graphql.execute_mutation(
            queries.ISSUE_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="issueCreate",
        )
        try:
            return MutationIssueResult.model_validate(result).issue
        except ValidationError as validation_error:
            raise CreateIssueError(
                "Linear returned an empty or incomplete issue create response"
            ) from validation_error

    async def update_issue(
        self, issue_id: str, payload: IssueUpdateMutationPayload
    ) -> MutationIssue:
        result = await self.graphql.execute_mutation(
            queries.ISSUE_UPDATE,
            {"id": issue_id, "input": payload.model_dump(exclude_none=True)},
            result_key="issueUpdate",
        )
        try:
            return MutationIssueResult.model_validate(result).issue
        except ValidationError as validation_error:
            raise UpdateIssueError(
                "Linear returned an empty or incomplete issue update response"
            ) from validation_error

    async def create_comment(
        self, payload: CommentCreateMutationPayload
    ) -> MutationComment:
        result = await self.graphql.execute_mutation(
            queries.COMMENT_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="commentCreate",
        )
        try:
            return MutationCommentResult.model_validate(result).comment
        except ValidationError as validation_error:
            raise LinearActionError(
                f"Could not add comment to issue '{payload.issueId}': Linear returned an empty or incomplete response"
            ) from validation_error

    @cache_coroutine_result()
    async def resolve_state_id(self, issue_id: str, state_name: str) -> str:
        data = await self.graphql.execute(
            queries.RESOLVE_STATE_BY_NAME,
            {"issueId": issue_id, "stateName": state_name},
        )
        try:
            result = ResolveStateByNameData.model_validate(data)
        except ValidationError as validation_error:
            raise LinearActionError(
                f"Could not resolve state '{state_name}' for issue '{issue_id}'"
            ) from validation_error

        states = result.issue.team.states.nodes
        if not states:
            raise LinearActionError(
                f"Could not find workflow state '{state_name}' for issue '{issue_id}'"
            )
        return states[0].id
