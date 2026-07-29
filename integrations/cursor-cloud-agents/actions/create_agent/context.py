from __future__ import annotations

from dataclasses import dataclass

from port_ocean.core.models import IntegrationRun

from actions.config_validation import parse_api_version
from actions.exceptions import InvalidActionParametersException


@dataclass(frozen=True)
class CreateAgentContext:
    run: IntegrationRun
    api_version: str
    report_completion: bool
    prompt: str | None
    repository: str | None
    ref: str | None
    pr_url: str | None
    model: object | None
    auto_create_pr: bool | None
    config: dict[str, object]

    @classmethod
    def from_run(cls, run: IntegrationRun) -> CreateAgentContext:
        props = run.execution_properties
        config = props.get("config")
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            raise InvalidActionParametersException("config must be an object")

        return cls(
            run=run,
            api_version=parse_api_version(props.get("apiVersion")),
            report_completion=bool(props.get("reportCompletion", False)),
            prompt=props.get("prompt"),
            repository=props.get("repository"),
            ref=props.get("ref"),
            pr_url=props.get("prUrl"),
            model=props.get("model"),
            auto_create_pr=props.get("autoCreatePr"),
            config=config,
        )
