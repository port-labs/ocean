import typing

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class JenkinsBuildSelector(Selector):
    query: str = Field(title="Query", description="The query to fetch Jenkins builds.")
    max_builds_per_job: int = Field(
        alias="maxBuildsPerJob",
        default=100,
        title="Max Builds Per Job",
        description="Number of builds to fetch. Defaults to 100",
        required=False,
    )


class JenkinsStageSelector(Selector):
    query: str = Field(title="Query", description="The query to fetch Jenkins stages.")
    job_url: str = Field(
        alias="jobUrl",
        title="Job URL",
        description="The URL of the Jenkins job to fetch stages for.",
        required=True,
    )


class JenkinsBuildResourceConfig(ResourceConfig):
    kind: typing.Literal["build"] = Field(
        title="Jenkins Build",
        description="Jenkins build resource kind.",
    )
    selector: JenkinsBuildSelector = Field(
        title="Build Selector",
        description="Selector for the Jenkins build resource.",
    )


class JenkinsStagesResourceConfig(ResourceConfig):
    kind: typing.Literal["stage"] = Field(
        title="Jenkins Stage",
        description="Jenkins stage resource kind.",
    )
    selector: JenkinsStageSelector = Field(
        title="Stage Selector",
        description="Selector for the Jenkins stage resource.",
    )


class JenkinsJobResourceConfig(ResourceConfig):
    kind: typing.Literal["job"] = Field(
        title="Jenkins Job",
        description="Jenkins job resource kind.",
    )


class JenkinsUserResourceConfig(ResourceConfig):
    kind: typing.Literal["user"] = Field(
        title="Jenkins User",
        description="Jenkins user resource kind.",
    )


class JenkinsPortAppConfig(PortAppConfig):
    resources: list[
        JenkinsBuildResourceConfig
        | JenkinsStagesResourceConfig
        | JenkinsJobResourceConfig
        | JenkinsUserResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]
