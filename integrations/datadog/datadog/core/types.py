from typing import Optional

from pydantic import BaseModel, validator


class AuditTrailAsset(BaseModel):
    type: str
    id: str

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


class AuditTrailUsr(BaseModel):
    uuid: Optional[str] = None
    id: Optional[str] = None


class AuditTrailAttributes(BaseModel):
    evt: AuditTrailEvt
    action: str
    asset: AuditTrailAsset
    usr: Optional[AuditTrailUsr] = None

    @validator("action", pre=True)
    @classmethod
    def normalize_action(cls, v: object) -> str:
        return str(v).lower()


class AuditTrailEvent(BaseModel):
    attributes: AuditTrailAttributes
