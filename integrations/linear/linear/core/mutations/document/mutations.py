from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations.document import queries
from linear.core.mutations.document.types import (
    DocumentCreateMutationPayload,
    MutationDocument,
    MutationDocumentResult,
)


class DocumentMutations(LinearExporter):
    object_type = LinearObject.DOCUMENTS

    async def create_document(
        self, payload: DocumentCreateMutationPayload
    ) -> MutationDocument:
        result = await self.graphql.execute_mutation(
            queries.DOCUMENT_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="documentCreate",
        )
        return MutationDocumentResult.model_validate(result).document
