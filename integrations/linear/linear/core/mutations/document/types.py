from pydantic import BaseModel

from linear.types import NonEmptyStr


class DocumentCreateMutationPayload(BaseModel):
    title: str
    content: str | None = None
    issueId: str | None = None
    projectId: str | None = None


class MutationDocument(BaseModel):
    id: NonEmptyStr
    title: NonEmptyStr
    url: NonEmptyStr | None = None


class MutationDocumentResult(BaseModel):
    success: bool
    document: MutationDocument
