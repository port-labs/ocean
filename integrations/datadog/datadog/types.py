from typing import Dict, NamedTuple

from pydantic import BaseModel, Field


class RestrictionPolicyResource(NamedTuple):
    type: str
    id: str


class OrgCredentials(BaseModel):
    """Per-organization Datadog credentials as supplied in datadogCredentialMap."""

    api_key: str = Field(..., alias="datadogApiKey")
    app_key: str = Field(..., alias="datadogApplicationKey")


class DatadogCredentialMap(BaseModel):
    """The datadogCredentialMap JSON: org uuid -> that org's credentials."""

    __root__: Dict[str, OrgCredentials]
