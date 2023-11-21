from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel
from jenkins_integration.utils import convert_timestamp_to_utc, sanitize_url
from port_ocean.context.ocean import ocean


class ObjectKind(Enum):
    BUILD = "build"
    JOB = "job"


class TimerTriggerCause(BaseModel):
    _class: str
    short_description: str


class BuildData(BaseModel):
    _class: str
    builds_by_branch_name: dict
    last_built_revision: dict
    remote_urls: List[str]
    scm_name: str


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
    display_name: str
    duration: int
    estimated_duration: int
    executor: dict
    full_display_name: str
    id: str
    in_progress: bool
    keep_log: bool
    number: int
    queue_id: int
    result: str
    timestamp: Union[int, str]
    built_on: str
    change_set: Optional[dict]
    culprits: List[Optional[dict]]

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.timestamp = self.time_as_datetime

    @property
    def time_as_datetime(self):
        return convert_timestamp_to_utc(self.timestamp)


class JenkinsJob(BaseModel):
    _class: str
    actions: List[Optional[dict]]
    description: str
    display_name: str
    display_name_or_null: str
    full_display_name: str
    full_name: str
    name: str
    health_report: List[Optional[dict]]


class JenkinsEvent(BaseModel):
    meta_data: Optional[dict]
    data: Union[JenkinsBuild, JenkinsBuild, dict]
    data_type: str
    url_data: str
    id: str
    source: str
    time: str
    type: str
    url: str
    full_url: Optional[str]

    def __init__(self, **data):
        super().__init__(**data)
        self.full_url = self.construct_full_url()

    def construct_full_url(self):
        return sanitize_url(f"{ocean.integration_config['jenkins_host']}/{self.url}")

    @property
    def kind(self):
        if self.type.startswith("item"):
            return ObjectKind.JOB
        elif self.type.startswith("run"):
            return ObjectKind.BUILD
        else:
            return None