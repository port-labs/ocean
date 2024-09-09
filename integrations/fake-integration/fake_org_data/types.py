from pydantic import BaseModel
from enum import StrEnum


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

    class Config:
        use_enum_values = True
