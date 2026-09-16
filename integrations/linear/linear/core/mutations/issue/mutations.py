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
)
from linear.helpers.exceptions import (
    CreateIssueError,
    LinearActionError,
    UpdateIssueError,
)


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
