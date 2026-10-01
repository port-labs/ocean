from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.exceptions import LinearActionError
from linear.actions.types import AddDocumentPayload
from linear.actions.utils import set_document_run_output
from linear.core.mutations import DocumentMutations


class AddDocumentExecutor(AbstractLinearExecutor):
    ACTION_NAME = "add_document"

    async def execute(self, run: IntegrationRun) -> None:
        payload = AddDocumentPayload.from_execution_properties(run.execution_properties)

        await ocean.port_client.post_run_log(
            run,
            f"Creating document '{payload.title}'",
            status_label="Creating document",
            should_raise=False,
        )

        mutations = DocumentMutations(self.client)
        try:
            document = await mutations.create_document(payload.to_mutation())
        except Exception as error:
            raise LinearActionError(str(error), status_label="Create failed") from error

        set_document_run_output(run, document)
        logger.info("Created Linear document", document_id=document.id)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Created document {document.id}: {document.url or document.title}",
            status_label="Document created",
        )
