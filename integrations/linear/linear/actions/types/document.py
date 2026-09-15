from typing import Self

from pydantic import model_validator

from linear.actions.types.base import LinearActionPayload, NonEmptyStr
from linear.core.mutations.document.types import DocumentCreateMutationPayload


class AddDocumentPayload(LinearActionPayload[DocumentCreateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = DocumentCreateMutationPayload

    title: NonEmptyStr
    content: NonEmptyStr | None = None
    issueId: NonEmptyStr | None = None
    projectId: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if not self.issueId and not self.projectId:
            raise ValueError("issueId or projectId is required")
        return self
