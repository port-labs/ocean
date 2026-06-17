from typing import List, NamedTuple, Optional

from pydantic import BaseModel, Field


class RestrictionPolicyResource(NamedTuple):
    type: str
    id: str


class OrgCredentials(BaseModel):
    """Per-organization Datadog credentials as supplied in datadogCredentialMap."""

    org_name: str = Field(..., alias="datadogOrgName")
    api_key: str = Field(..., alias="datadogApiKey")
    app_key: str = Field(..., alias="datadogApplicationKey")
    # Orgs can live on different Datadog sites (us3, eu, ...). Falls back to the
    # integration's datadogBaseUrl when omitted.
    base_url: Optional[str] = Field(None, alias="datadogBaseUrl")


class DatadogCredentialMap(BaseModel):
    """The datadogCredentialMap JSON: a list of per-org credentials.

    A list (not a dict keyed by org) because org names aren't unique — several
    entries may share a name, and routing tries each candidate in turn.
    """

    __root__: List[OrgCredentials]
