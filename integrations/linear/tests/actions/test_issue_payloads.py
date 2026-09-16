from typing import TypeVar

import pytest
from pydantic import BaseModel

from linear.actions.types.base import LinearActionPayload, MutationPayloadT
from linear.actions.types.issue import (
    AddIssueCommentPayload,
    AddReactionPayload,
    CreateIssuePayload,
    CreateSubIssuePayload,
    UpdateIssuePayload,
)
from linear.core.mutations.issue.types import (
    CommentCreateMutationPayload,
    IssueCreateMutationPayload,
    IssueUpdateMutationPayload,
)
from linear.core.mutations.reaction.types import ReactionCreateMutationPayload
from linear.utils import PRIORITY_BY_LABEL, PriorityLabel

ActionPayloadT = TypeVar("ActionPayloadT", bound=LinearActionPayload[BaseModel])


@pytest.mark.parametrize(
    ("action_cls", "properties", "mutation_cls", "expected"),
    [
        pytest.param(
            CreateIssuePayload,
            {
                "teamId": "team-1",
                "title": "Bug",
                "description": "desc",
                "assigneeId": "user-1",
                "stateId": "state-1",
                "projectId": "proj-1",
                "cycleId": "cycle-1",
                "priority": PriorityLabel.HIGH,
                "labelIds": ["label-1"],
            },
            IssueCreateMutationPayload,
            {
                "teamId": "team-1",
                "title": "Bug",
                "description": "desc",
                "assigneeId": "user-1",
                "stateId": "state-1",
                "projectId": "proj-1",
                "cycleId": "cycle-1",
                "priority": PRIORITY_BY_LABEL[PriorityLabel.HIGH],
                "labelIds": ["label-1"],
            },
            id="create_issue",
        ),
        pytest.param(
            CreateSubIssuePayload,
            {
                "parentId": "ENG-1",
                "title": "Sub task",
                "teamId": "team-1",
                "description": "desc",
                "assigneeId": "user-1",
                "stateId": "state-1",
                "priority": PriorityLabel.URGENT,
            },
            IssueCreateMutationPayload,
            {
                "parentId": "ENG-1",
                "title": "Sub task",
                "teamId": "team-1",
                "description": "desc",
                "assigneeId": "user-1",
                "stateId": "state-1",
                "priority": PRIORITY_BY_LABEL[PriorityLabel.URGENT],
            },
            id="create_sub_issue",
        ),
        pytest.param(
            UpdateIssuePayload,
            {
                "issueId": "ENG-1",
                "title": "Updated",
                "description": "desc",
                "assigneeId": "user-1",
                "stateId": "state-1",
                "projectId": "proj-1",
                "cycleId": "cycle-1",
                "priority": PriorityLabel.LOW,
                "delegateId": "delegate-1",
                "labelIds": ["label-1"],
            },
            IssueUpdateMutationPayload,
            {
                "title": "Updated",
                "description": "desc",
                "assigneeId": "user-1",
                "stateId": "state-1",
                "projectId": "proj-1",
                "cycleId": "cycle-1",
                "priority": PRIORITY_BY_LABEL[PriorityLabel.LOW],
                "delegateId": "delegate-1",
                "labelIds": ["label-1"],
            },
            id="update_issue",
        ),
        pytest.param(
            AddIssueCommentPayload,
            {"issueId": "ENG-1", "body": "Looks good"},
            CommentCreateMutationPayload,
            {"issueId": "ENG-1", "body": "Looks good"},
            id="add_issue_comment",
        ),
        pytest.param(
            AddReactionPayload,
            {"issueId": "ENG-1", "emoji": "+1"},
            ReactionCreateMutationPayload,
            {"issueId": "ENG-1", "emoji": "+1"},
            id="add_reaction_to_issue",
        ),
    ],
)
def test_issue_payload_to_mutation_contract(
    action_cls: type[ActionPayloadT],
    properties: dict[str, object],
    mutation_cls: type[MutationPayloadT],
    expected: dict[str, object],
) -> None:
    action_payload = action_cls.from_execution_properties(properties)

    mutation_payload = action_payload.to_mutation()

    assert isinstance(mutation_payload, mutation_cls)
    assert action_cls.MUTATION_PAYLOAD_TYPE is mutation_cls
    assert mutation_payload.model_dump(exclude_none=True) == expected
