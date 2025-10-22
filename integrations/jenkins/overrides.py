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
        days_since: int = Field(
            alias="daysSince",
            required=False,
            default=1,
            description="Number of days to fetch builds for. Defaults to 1",
        )
        job_filter: list[str] = Field(
            alias="jobFilter",
            required=False,
            default_factory=list,
            description="List of job names to fetch builds for. Defaults to empty list",
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
