from typing import ClassVar, Self

from pydantic import model_validator

from linear.actions.types.base import LinearActionPayload
from linear.types import NonEmptyStr
from linear.core.mutations.document.types import DocumentCreateMutationPayload

DOCUMENT_TARGET_FIELDS = (
    "initiativeId",
    "teamId",
    "issueId",
    "releaseId",
    "cycleId",
    "projectId",
)


class AddDocumentPayload(LinearActionPayload[DocumentCreateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = DocumentCreateMutationPayload
    DOCUMENT_TARGET_FIELDS: ClassVar[tuple[str, ...]] = DOCUMENT_TARGET_FIELDS

    title: NonEmptyStr
    content: NonEmptyStr | None = None
    initiativeId: NonEmptyStr | None = None
    teamId: NonEmptyStr | None = None
    issueId: NonEmptyStr | None = None
    releaseId: NonEmptyStr | None = None
    cycleId: NonEmptyStr | None = None
    projectId: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_exactly_one_target(self) -> Self:
        set_targets = [
            field for field in self.DOCUMENT_TARGET_FIELDS if getattr(self, field)
        ]
        if not set_targets:
            raise ValueError(
                "Exactly one of initiativeId, teamId, issueId, releaseId, cycleId, or projectId is required"
            )
        if len(set_targets) > 1:
            raise ValueError(
                f"Only one document target is allowed, got: {', '.join(set_targets)}"
            )
        return self
