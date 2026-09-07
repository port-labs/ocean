from typing import Any

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations import queries
from linear.helpers.exceptions import LinearActionError


class DocumentMutations(LinearExporter):
    object_type = LinearObject.DOCUMENTS

    async def create_document(self, document_input: dict[str, Any]) -> dict[str, Any]:
        result = await self.graphql.execute_mutation(
            queries.DOCUMENT_CREATE,
            {"input": document_input},
            result_key="documentCreate",
        )
        document = result.get("document")
        if not isinstance(document, dict) or not document.get("id"):
            raise LinearActionError(
                "Could not create document: Linear returned an empty or incomplete response"
            )
        return document
