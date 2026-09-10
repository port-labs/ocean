from unittest.mock import MagicMock, patch

import pytest

from linear.actions.add_document_executor import AddDocumentExecutor
from linear.helpers.exceptions import MissingExecutionPropertyError
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestAddDocumentExecutor:
    async def test_requires_issue_or_project(
        self, mock_port_client: MagicMock, mock_linear_client: MagicMock
    ) -> None:
        executor = create_executor(AddDocumentExecutor, mock_linear_client)
        run = make_run("add_document", {"title": "Notes"})
        with patch("linear.actions.add_document_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)
