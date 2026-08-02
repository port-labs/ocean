from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SkipValidation,
    ValidationError,
    field_validator,
    model_validator,
)
from port_ocean.core.models import IntegrationRun

from actions.exceptions import InvalidActionParametersException

API_VERSION_V0 = "v0"
API_VERSION_V1 = "v1"
_SUPPORTED_API_VERSIONS = frozenset({API_VERSION_V0, API_VERSION_V1})


def _parse_api_version(raw: object) -> str:
    if raw is None:
        return API_VERSION_V1
    if not isinstance(raw, str):
        raise InvalidActionParametersException("apiVersion must be a string")
    normalized = raw.strip().lower()
    if normalized not in _SUPPORTED_API_VERSIONS:
        raise InvalidActionParametersException(
            f"apiVersion must be {API_VERSION_V0!r} or {API_VERSION_V1!r}"
        )
    return normalized


class CreateAgentContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run: SkipValidation[IntegrationRun]
    api_version: str = API_VERSION_V1
    report_completion: bool = False
    prompt: str | None = None
    repository: str | None = None
    ref: str | None = None
    pr_url: str | None = None
    model: object | None = None
    auto_create_pr: bool | None = None
    config: dict[str, object] = Field(default_factory=dict)

    @field_validator("api_version", mode="before")
    @classmethod
    def _normalize_api_version(cls, raw: object) -> str:
        return _parse_api_version(raw)

    @field_validator("config", mode="before")
    @classmethod
    def _normalize_config(cls, raw: object) -> dict[str, object]:
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise InvalidActionParametersException("config must be an object")
        return raw

    @model_validator(mode="after")
    def _validate_report_completion_policy(self) -> Self:
        if self.api_version == API_VERSION_V1 and self.report_completion:
            raise InvalidActionParametersException(
                "reportCompletion is only supported on create_agent with apiVersion v0 "
                "(v1 has no webhooks)"
            )
        return self

    @classmethod
    def from_run(cls, run: IntegrationRun) -> CreateAgentContext:
        props = run.execution_properties
        try:
            return cls(
                run=run,
                api_version=_parse_api_version(props.get("apiVersion")),
                report_completion=bool(props.get("reportCompletion", False)),
                prompt=props.get("prompt"),
                repository=props.get("repository"),
                ref=props.get("ref"),
                pr_url=props.get("prUrl"),
                model=props.get("model"),
                auto_create_pr=props.get("autoCreatePr"),
                config=props.get("config", {}),
            )
        except ValidationError as error:
            for item in error.errors():
                if isinstance(
                    item.get("ctx", {}).get("error"), InvalidActionParametersException
                ):
                    raise item["ctx"]["error"] from error
            first = error.errors()[0]
            message = first.get("msg")
            if not isinstance(message, str):
                message = str(message)
            raise InvalidActionParametersException(message) from error
        except InvalidActionParametersException:
            raise
