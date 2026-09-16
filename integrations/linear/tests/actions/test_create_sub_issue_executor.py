from unittest.mock import MagicMock, patch

import pytest

from linear.actions.create_sub_issue_executor import CreateSubIssueExecutor
from linear.core.mutations.issue.types import IssueCreateMutationPayload
from linear.actions.exceptions import MissingExecutionPropertyError
from tests.actions.conftest import create_executor, make_run


@pytest.mark.asyncio
class TestCreateSubIssueExecutor:
    async def test_resolves_team_from_parent(
        self,
        mock_port_client: MagicMock,
        mock_linear_client: MagicMock,
        mock_issue_mutations: MagicMock,
        mock_issue_exporter: MagicMock,
    ) -> None:
        executor = create_executor(CreateSubIssueExecutor, mock_linear_client)
        run = make_run(
            "create_sub_issue",
            {
                "parentId": "ENG-1",
                "title": "Sub task",
                "projectId": "not-in-contract",
            },
        )
        with (
            patch("linear.actions.create_sub_issue_executor.ocean") as mock_ocean,
            patch(
                "linear.actions.create_sub_issue_executor.IssueMutations",
                return_value=mock_issue_mutations,
            ),
            patch(
                "linear.actions.create_sub_issue_executor.IssueExporter",
                return_value=mock_issue_exporter,
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_issue_exporter.get_resource.assert_awaited_once()
        create_payload = mock_issue_mutations.create_issue.await_args.args[0]
        assert isinstance(create_payload, IssueCreateMutationPayload)
        mutation_payload = create_payload.model_dump(exclude_none=True)
        assert mutation_payload["teamId"] == "team-1"
        assert mutation_payload["parentId"] == "ENG-1"
        assert "projectId" not in mutation_payload
        assert run.output == {
            "identifier": "ENG-1",
            "issueId": "issue-1",
            "issueUrl": "https://linear.app/test/issue/ENG-1",
        }
        mock_port_client.post_run_log.assert_any_call(
            run,
            "Creating sub-issue 'Sub task' under ENG-1",
            should_raise=False,
        )
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Created sub-issue ENG-1: https://linear.app/test/issue/ENG-1",
            status_label="Issue created",
        )

    @pytest.mark.parametrize(
        "properties",
        [
            {"title": "Sub task"},
            {"parentId": "ENG-1"},
        ],
    )
    async def test_requires_inputs(
        self,
        properties: dict[str, str],
        mock_linear_client: MagicMock,
    ) -> None:
        executor = create_executor(CreateSubIssueExecutor, mock_linear_client)

        with pytest.raises(MissingExecutionPropertyError):
            await executor.execute(make_run("create_sub_issue", properties))
