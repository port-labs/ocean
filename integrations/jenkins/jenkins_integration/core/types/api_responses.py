from typing import List, Literal, TypedDict


BuildResult = Literal["SUCCESS", "FAILURE", "UNSTABLE"]


class LastBuildAPIResponse(TypedDict):
    _class: str
    result: BuildResult
    timestamp: int


class JobAPIResponse(TypedDict):
    _class: str
    name: str
    url: str
    lastBuild: LastBuildAPIResponse


class JobListAPIResponse(TypedDict):
    _class: str
    jobs: List[JobAPIResponse]


class BuildAPIResponse(TypedDict):
    _class: str
    id: str
    result: BuildResult
    url: str
    timestamp: int
    duration: int
    fullDisplayName: str


class BuildListAPIResponse(TypedDict):
    _class: str
    builds: List[BuildAPIResponse]
