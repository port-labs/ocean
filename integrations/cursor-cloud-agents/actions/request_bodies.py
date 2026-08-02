from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    ValidationInfo,
    model_validator,
)

from actions.exceptions import InvalidActionParametersException


class PromptImageBody(BaseModel):
    """Cursor prompt image (base64 `data` + `mimeType`, or `url`)."""

    model_config = ConfigDict(extra="allow")

    data: str | None = None
    mimeType: str | None = None
    url: str | None = None


class PromptBody(BaseModel):
    """Cursor prompt object (POST body). Images belong under prompt, not at body root."""

    model_config = ConfigDict(extra="allow")

    text: str
    images: list[PromptImageBody] | None = None


class V0SourceBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    repository: str | None = None
    ref: str | None = None
    prUrl: str | None = None


class V0TargetBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    branchName: str | None = None
    openAsCursorGithubApp: bool | None = None
    skipReviewerRequest: bool | None = None
    autoBranch: bool | None = None
    autoCreatePr: bool | None = None


class WebhookBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str
    secret: str


class V0CreateAgentBody(BaseModel):
    """POST /v0/agents request body after Port field mapping and config merge."""

    model_config = ConfigDict(extra="allow")

    prompt: PromptBody
    source: V0SourceBody | None = None
    target: V0TargetBody | None = None
    model: str | None = None
    webhook: WebhookBody | None = None

    @model_validator(mode="after")
    def port_rejects_user_webhook_with_report_completion(
        self, info: ValidationInfo
    ) -> Self:
        report_completion = (
            info.context.get("report_completion", False) if info.context else False
        )
        if report_completion and self.webhook is not None:
            raise ValueError(
                "config.webhook cannot be set when reportCompletion is true; "
                "the integration owns the webhook used for completion tracking"
            )
        return self


class ModelParamBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    value: str


class V1ModelBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    params: list[ModelParamBody] | None = None


class RepoBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str
    startingRef: str | None = None
    prUrl: str | None = None


class EnvBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    name: str | None = None


class McpServerBody(BaseModel):
    """Inline MCP server definition (POST /v1/agents and follow-up runs)."""

    model_config = ConfigDict(extra="allow")

    name: str


class CustomSubagentBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str
    prompt: str
    model: str | V1ModelBody | None = None


class V1CreateAgentBody(BaseModel):
    """POST /v1/agents request body after Port field mapping and config merge."""

    model_config = ConfigDict(extra="allow")

    prompt: PromptBody
    repos: list[RepoBody] | None = None
    env: EnvBody | None = None
    model: V1ModelBody | None = None
    mcpServers: list[McpServerBody] | None = None
    customSubagents: list[CustomSubagentBody] | None = None
    envVars: dict[str, str] | None = None
    mode: str | None = None
    workOnCurrentBranch: bool | None = None
    name: str | None = None
    autoCreatePR: bool | None = None
    skipReviewerRequest: bool | None = None
    agentId: str | None = None

    @model_validator(mode="after")
    def port_requires_workspace(self) -> Self:
        has_repos = isinstance(self.repos, list) and len(self.repos) > 0
        has_env = self.env is not None
        if not has_repos and not has_env:
            raise ValueError(
                "create_agent with apiVersion v1 requires a workspace: "
                "set repository, config.repos, or config.env"
            )
        return self


class V1CreateRunBody(BaseModel):
    """POST /v1/agents/{agentId}/runs request body after config merge."""

    model_config = ConfigDict(extra="allow")

    prompt: PromptBody
    mcpServers: list[McpServerBody] | None = None
    mode: str | None = None


def _validation_error_message(error: ValidationError) -> str:
    first_error = error.errors()[0]
    message = first_error.get("msg", "Invalid request body")
    if message.startswith("Value error, "):
        message = message.removeprefix("Value error, ")
    loc = first_error.get("loc", ())
    if loc:
        path = ".".join(str(part) for part in loc)
        return f"{path}: {message}"
    return str(message)


def parse_v0_create_body(
    body: dict[str, object],
    *,
    report_completion: bool,
) -> V0CreateAgentBody:
    try:
        return V0CreateAgentBody.model_validate(
            body,
            context={"report_completion": report_completion},
        )
    except ValidationError as error:
        raise InvalidActionParametersException(
            _validation_error_message(error)
        ) from error


def parse_v1_create_body(body: dict[str, object]) -> V1CreateAgentBody:
    try:
        return V1CreateAgentBody.model_validate(body)
    except ValidationError as error:
        raise InvalidActionParametersException(
            _validation_error_message(error)
        ) from error


def parse_v1_run_body(body: dict[str, object]) -> V1CreateRunBody:
    try:
        return V1CreateRunBody.model_validate(body)
    except ValidationError as error:
        raise InvalidActionParametersException(
            _validation_error_message(error)
        ) from error
