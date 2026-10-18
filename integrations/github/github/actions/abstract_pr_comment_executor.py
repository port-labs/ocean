from abc import abstractmethod
from typing import Any, ClassVar, Generic, TypeVar

import httpx
from pydantic import Field

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import CommentActionError
from github.clients.http.rest_client import GithubRestClient


class PrCommentInputs(AbstractGithubActionInput):
    org: str = Field(min_length=1)
    repo: str = Field(min_length=1)

    @property
    def repo_path(self) -> str:
        return f"{self.org}/{self.repo}"


InputsT = TypeVar("InputsT", bound=PrCommentInputs)


class AbstractPrCommentExecutor(AbstractGithubExecutor, Generic[InputsT]):
    """Shared flow for PR comment actions, which use GitHub's issue comments API."""

    INPUTS_CLASS: ClassVar[type[PrCommentInputs]]
    ERROR_CLASS: ClassVar[type[CommentActionError]]
    IN_PROGRESS_STATUS_LABEL: ClassVar[str]
    COMPLETED_STATUS_LABEL: ClassVar[str]

    @abstractmethod
    def _start_message(self, inputs: InputsT) -> str: ...

    @abstractmethod
    async def _perform(self, rest_client: GithubRestClient, inputs: InputsT) -> str:
        """Call GitHub and return the success message reported to Port."""

    async def execute(self, run: IntegrationRun) -> None:
        inputs: InputsT = self.INPUTS_CLASS.from_execution_properties(  # type: ignore[assignment]
            run.execution_properties
        )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            self._start_message(inputs),
            status_label=self.IN_PROGRESS_STATUS_LABEL,
            should_raise=False,
        )

        message = await self._perform(rest_client, inputs)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label=self.COMPLETED_STATUS_LABEL,
        )

    def _repo_url(self, rest_client: GithubRestClient, inputs: InputsT) -> str:
        return f"{rest_client.base_url}/repos/{inputs.repo_path}"

    async def _write_comment(
        self,
        rest_client: GithubRestClient,
        url: str,
        method: str,
        body: str,
        error_prefix: str,
    ) -> tuple[Any, str]:
        """Create or update a comment and return its id and html_url."""
        try:
            comment = await rest_client.send_api_request(
                url,
                method=method,
                json_data={"body": body},
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise self.ERROR_CLASS.from_response(e.response, error_prefix)

        comment_id = comment.get("id")
        html_url = comment.get("html_url")
        if comment_id is None or html_url is None:
            raise self.ERROR_CLASS(
                f"{error_prefix}: GitHub returned an empty or incomplete response"
            )
        return comment_id, html_url
