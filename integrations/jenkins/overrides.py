import typing

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class JenkinsBuildResourceConfig(ResourceConfig):
    class JenkinsBuildSelector(Selector):
        query: str
        max_builds_per_job: int = Field(
            alias="maxBuildsPerJob",
            required=False,
            default=100,
            description="Number of builds to fetch. Defaults to 100",
        )

    kind: typing.Literal["build"]
    selector: JenkinsBuildSelector


class JenkinStagesResourceConfig(ResourceConfig):
    class JenkinStageSelector(Selector):
        query: str
        job_url: str = Field(alias="jobUrl", required=True)

    kind: typing.Literal["stage"]
    selector: JenkinStageSelector


class JenkinsPortAppConfig(PortAppConfig):
    resources: list[
        JenkinStagesResourceConfig | JenkinsBuildResourceConfig | ResourceConfig
    ] = Field(default_factory=list)
