from unittest.mock import MagicMock, patch

import pytest

from linear.actions.add_document_executor import AddDocumentExecutor
from linear.core.mutations.document.types import DocumentCreateMutationPayload
from linear.actions.exceptions import MissingExecutionPropertyError
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestAddDocumentExecutor:
    async def test_happy_path(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_document_mutations: MagicMock,
    ) -> None:
        executor = create_executor(AddDocumentExecutor, mock_linear_client)
        run = make_run(
            "add_document",
            {"title": "Notes", "content": "Details", "issueId": "ENG-1"},
        )
        with (
            patch("linear.actions.add_document_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.add_document_executor.DocumentMutations",
                return_value=mock_document_mutations,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_document_mutations.create_document.assert_awaited_once()
        create_payload = mock_document_mutations.create_document.await_args.args[0]
        assert isinstance(create_payload, DocumentCreateMutationPayload)
        assert create_payload.model_dump(exclude_none=True) == {
            "title": "Notes",
            "content": "Details",
            "issueId": "ENG-1",
        }
        assert run.output == {
            "documentId": "doc-1",
            "documentUrl": "https://linear.app/test/document/doc-1",
            "title": "Notes",
        }
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Created document doc-1: https://linear.app/test/document/doc-1",
            status_label="Document created",
        )

    async def test_requires_exactly_one_target(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(AddDocumentExecutor, mock_linear_client)
        run = make_run("add_document", {"title": "Notes"})
        with patch("linear.actions.add_document_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError, match="Exactly one of"):
                await executor.execute(run)

    async def test_rejects_multiple_targets(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(AddDocumentExecutor, mock_linear_client)
        run = make_run(
            "add_document",
            {"title": "Notes", "issueId": "ENG-1", "projectId": "proj-1"},
        )
        with patch("linear.actions.add_document_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(
                MissingExecutionPropertyError, match="Only one document"
            ):
                await executor.execute(run)
