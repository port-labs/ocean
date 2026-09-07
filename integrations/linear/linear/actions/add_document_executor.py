from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import optional_string, require_property
from linear.core.mutations import DocumentMutations
from linear.helpers.exceptions import MissingExecutionPropertyError


class AddDocumentExecutor(AbstractLinearExecutor):
    ACTION_NAME = "add_document"

    async def execute(self, run: IntegrationRun) -> None:
        title = require_property(run, "title")
        content = optional_string(run.execution_properties.get("content"))
        issue_id = optional_string(run.execution_properties.get("issueId"))
        project_id = optional_string(run.execution_properties.get("projectId"))

        if not issue_id and not project_id:
            raise MissingExecutionPropertyError("issueId or projectId is required")

        document_input: dict[str, str] = {"title": str(title)}
        if content:
            document_input["content"] = content
        if issue_id:
            document_input["issueId"] = issue_id
        if project_id:
            document_input["projectId"] = project_id

        await ocean.port_client.post_run_log(
            run,
            f"Creating document '{title}'",
            should_raise=False,
        )

        mutations = DocumentMutations(self.client)
        document = await mutations.create_document(document_input)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Created document {document['id']}: {document.get('url', document['title'])}",
        )
        logger.info("Created Linear document", document_id=document["id"])
