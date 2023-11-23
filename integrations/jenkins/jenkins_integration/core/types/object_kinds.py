from typing import TypedDict

from jenkins_integration.core.types.api_responses import BuildResult


class ObjectKind:
    BUILD = "build"
    JOB = "job"


class JenkinsBuild(TypedDict):
    id: str
    name: str
    status: BuildResult
    timestamp: str
    url: str
    duration: str


class JenkinsJob(TypedDict):
    name: str
    status: BuildResult
    timestamp: str
    url: str
