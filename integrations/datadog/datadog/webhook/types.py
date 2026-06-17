from typing import Optional

from pydantic import BaseModel, validator


class AuditTrailAsset(BaseModel):
    type: str
    id: str
    name: Optional[str] = None

    @validator("type", pre=True)
    @classmethod
    def normalize_type(cls, v: object) -> str:
        return str(v).lower()


class AuditTrailEvt(BaseModel):
    name: str

    @validator("name", pre=True)
    @classmethod
    def normalize_name(cls, v: object) -> str:
        return str(v).strip()


class AuditTrailHttp(BaseModel):
    class UrlDetails(BaseModel):
        path: str

    url_details: UrlDetails


class AuditTrailOrg(BaseModel):
    name: str
    uuid: Optional[str] = None


class AuditTrailAttributes(BaseModel):
    evt: AuditTrailEvt
    action: str
    asset: AuditTrailAsset
    org: Optional[AuditTrailOrg] = None
    http: Optional[AuditTrailHttp] = None

    @validator("action", pre=True)
    @classmethod
    def normalize_action(cls, v: object) -> str:
        return str(v).lower()


class AuditTrailEvent(BaseModel):
    attributes: AuditTrailAttributes
    message: Optional[str] = None
