import typing

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class JenkinStagesResourceConfig(ResourceConfig):
    class JenkinStageSelector(Selector):
        query: str
        job_url: str = Field(alias="jobUrl", required=True)

    kind: typing.Literal["stage"]
    selector: JenkinStageSelector


class JenkinsPortAppConfig(PortAppConfig):
    resources: list[JenkinStagesResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )
