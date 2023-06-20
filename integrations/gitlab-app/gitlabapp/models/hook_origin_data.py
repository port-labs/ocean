from typing import Optional

from pydantic import BaseModel, Field


class HookOriginData(BaseModel):
    # event_id: Optional[str] = Field(..., alias='eventId')
    event_name: Optional[str] = Field(..., alias="eventName")
    group_id: str = Field(..., alias="groupId")
    installation_id: Optional[str] = Field(..., alias="installationId")
    org_id: Optional[str] = Field(..., alias="orgId")
