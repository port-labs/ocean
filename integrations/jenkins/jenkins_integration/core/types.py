from typing import Literal, TypedDict

BuildResult = Literal["SUCCESS", "FAILURE", "UNSTABLE"]


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
    jobUrl: str


class JenkinsJob(TypedDict):
    name: str
    status: BuildResult
    timestamp: str
    url: str
