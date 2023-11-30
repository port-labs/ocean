from enum import StrEnum
from typing import List, Optional, Union

from core.utils import sanitize_url, convert_timestamp_to_utc_dt
from pydantic import BaseModel

from port_ocean.context.ocean import ocean


class ObjectKind(StrEnum):
    BUILD = "build"
    JOB = "job"


class JenkinsEvent(BaseModel):
    metaData: Optional[dict]
    data: dict
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
        return sanitize_url(f"{ocean.integration_config['jenkins_host']}/{self.url}")

    @property
    def kind(self):
        if self.type.startswith("item"):
            return ObjectKind.JOB
        elif self.type.startswith("run"):
            return ObjectKind.BUILD
        else:
            return None  # or any other default value
