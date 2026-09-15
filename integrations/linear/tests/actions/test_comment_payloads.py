from typing import TypeVar

import pytest
from pydantic import BaseModel

from linear.actions.types.base import LinearActionPayload, MutationPayloadT
from linear.actions.types.comment import AddCommentPayload
from linear.core.mutations.comment.types import CommentCreateMutationPayload

ActionPayloadT = TypeVar("ActionPayloadT", bound=LinearActionPayload[BaseModel])


@pytest.mark.parametrize(
    ("action_cls", "properties", "mutation_cls", "expected"),
    [
        pytest.param(
            AddCommentPayload,
            {"issueId": "ENG-1", "body": "Looks good"},
            CommentCreateMutationPayload,
            {"issueId": "ENG-1", "body": "Looks good"},
            id="add_comment",
        ),
    ],
)
def test_comment_payload_to_mutation_contract(
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
