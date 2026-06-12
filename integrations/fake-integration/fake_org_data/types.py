from enum import StrEnum
from typing import Optional

from pydantic import BaseModel


class FakePersonStatus(StrEnum):
    WORKING = "WORKING"
    NOPE = "NOPE"


class FakeDepartment(BaseModel):
    id: str
    name: str


class FakePerson(BaseModel):
    id: str
    email: str
    name: str
    status: FakePersonStatus
    age: int
    department: FakeDepartment
    bio: str

    class Config:
        use_enum_values = True


class Geo(BaseModel):
    lat: float
    lng: float


class Address(BaseModel):
    city: str
    country: str
    lines: list[str]
    geo: Geo


class FakeOffice(BaseModel):
    id: str
    name: str
    address: Address


class FakeLead(BaseModel):
    name: str
    email: str


class FakeTeam(BaseModel):
    id: str
    name: str
    department: FakeDepartment
    lead: FakeLead


class FakeOwner(BaseModel):
    id: str
    name: str
    department: FakeDepartment


class ProjectTier(BaseModel):
    level: str


class ProjectMetadata(BaseModel):
    tier: ProjectTier


class FakeProject(BaseModel):
    id: str
    name: str
    owner: FakeOwner
    metadata: Optional[ProjectMetadata] = None
