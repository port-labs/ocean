from pydantic import BaseModel, Field
from enum import StrEnum
from typing import List, Optional, Literal
from port_ocean.core.handlers.port_app_config.models import Selector


class FakePersonStatus(StrEnum):
    WORKING = "WORKING"
    NOPE = "NOPE"


class FakeProject(BaseModel):
    id: str
    name: str
    status: str
    description: str


class FakeDepartment(BaseModel):
    id: str
    name: str
    members: Optional[List[str]] = None  # List of person IDs for itemsToParse testing


class FakePerson(BaseModel):
    id: str
    email: str
    name: str
    status: FakePersonStatus
    age: int
    department: FakeDepartment
    bio: str
    projects: Optional[List[FakeProject]] = None  # For itemsToParse testing

    class Config:
        use_enum_values = True


class FakeRepository(BaseModel):
    id: str
    name: str
    status: str
    language: str
    url: str
    owner: Optional[FakePerson] = None  # For relation testing
class FakeObjectKind(StrEnum):
    FAKE_DEPARTMENT = "fake-department"
    FAKE_PERSON = "fake-person"
    FAKE_REPOSITORY = "fake-repository"
    FAKE_FILE = "fake-file"
    INVOKE_FAKE_WEBHOOK_EVENT = "invoke-fake-webhook-event"


class FakeSelector(Selector):
    """Selector for fake integration resources - extends Selector with fake-specific fields"""

    entity_count: int = Field(
        default=20, description="Number of entities to fetch", alias="entityCount"
    )
    entity_size_kb: int = Field(
        default=1, description="Size of entity in KB", alias="entitySizeKb"
    )
    batch_count: int = Field(
        default=1, description="Number of batches", alias="batchCount"
    )
    items_to_parse_entity_count: int = Field(
        default=1,
        description="Number of entities to parse",
        alias="itemsToParseEntityCount",
    )
    items_to_parse_entity_size_kb: int = Field(
        default=1,
        description="Size of entity to parse in KB",
        alias="itemsToParseEntitySizeKb",
    )
    delay_ms: int = Field(
        default=0, description="Delay in milliseconds between entities", alias="delayMs"
    )

    file_path: str = Field(
        default="readme.md", description="Path of file to fetch", alias="filePath"
    )
    file_size_kb: int = Field(
        default=1, description="Size of file in KB", alias="fileSizeKb"
    )

    codeowners_row_count: int = Field(
        default=10,
        description="Number of rows in codeowners file",
        alias="codeownersRowCount",
    )
    webhook_action: Literal["create", "update", "delete"] = Field(
        default="create",
        description="Action to perform on webhook",
        alias="webhookAction",
    )


class FakeIntegrationConfig(FakeSelector):
    """Configuration model for fake integration (used internally)"""

    pass
