from enum import StrEnum
from typing import List, Optional, Union
from datetime import datetime, timezone

from loguru import logger
from port_ocean.context.ocean import ocean
from pydantic import BaseModel

from core.utils import sanitize_url


class ObjectKind(StrEnum):
    BUILD = "build"
    JOB = "job"


class TimerTriggerCause(BaseModel):
    _class: str
    shortDescription: str


class BuildData(BaseModel):
    _class: str
    buildsByBranchName: dict
    lastBuiltRevision: dict
    remoteUrls: List[str]
    scmName: str


class RunDisplayAction(BaseModel):
    _class: str


class ChangeLogSet(BaseModel):
    _class: str
    items: List[dict]
    kind: str


class JenkinsBuild(BaseModel):
    _class: str
    actions: List[Optional[dict]]
    artifacts: List[Optional[dict]]
    building: bool
    description: Optional[str]
    displayName: str
    duration: int
    estimatedDuration: int
    executor: dict
    fullDisplayName: str
    id: str
    inProgress: bool
    keepLog: bool
    number: int
    queueId: int
    result: str
    timestamp: int | str
    builtOn: str
    changeSet: Optional[dict]
    culprits: List[Optional[dict]]

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.timestamp = self.time_as_datetime

    @property
    def time_as_datetime(self):
        try:
            # Convert timestamp to datetime object
            dt_object = datetime.fromtimestamp(self.timestamp / 1000.0, tz=timezone.utc)

            # Format datetime object as a string
            formatted_string = dt_object.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
            return formatted_string
        except Exception as e:
            logger.exception(e)


class JenkinsJob(BaseModel):
    """
    A jenkins job could have many more attributes but these are expected in every item
    """
    _class: str
    actions: List[Optional[dict]]
    description: str
    displayName: str
    displayNameOrNull: str
    fullDisplayName: str
    fullName: str
    name: str
    healthReport: List[Optional[dict]]


class JenkinsEvent(BaseModel):
    metaData: Optional[dict]
    data: Union[JenkinsBuild, JenkinsBuild, dict]
    dataType: str
    urlData: str
    id: str
    source: str
    time: str
    type: str
    url: str
    fullUrl: Optional[str]

    def __init__(self, **data):
        super().__init__(**data)
        self.fullUrl = self.construct_full_url()

    def construct_full_url(self):
        # Replace this with your logic to construct the full URL based on available information
        return sanitize_url(f"{ocean.integration_config['jenkins_host']}/{self.url}")

    @property
    def kind(self):
        if self.type.startswith("item"):
            return ObjectKind.JOB
        elif self.type.startswith("run"):
            return ObjectKind.BUILD
        else:
            return None  # or any other default value
