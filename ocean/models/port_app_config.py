from typing import List, Optional

from pydantic import BaseModel, Field


class EntityMapping(BaseModel):
    identifier: str
    title: str
    blueprint: str
    properties: dict = Field(default_factory=dict)


class PortResourceConfig(BaseModel):
    class MappingsConfig(BaseModel):
        mappings: EntityMapping

    entity: Optional[MappingsConfig]
    blueprint: Optional[MappingsConfig]


class ResourceConfig(BaseModel):
    class Selector(BaseModel):
        query: str

    kind: str
    selector: Selector
    port: PortResourceConfig


class PortAppConfig(BaseModel):
    spec_path: str | List[str] = Field(..., alias="specPath")
    branch: str = "main"
    enable_merge_entity: bool = Field(..., alias="enableMergeEntity")
    delete_dependent_entities: bool = Field(..., alias="deleteDependentEntities")
    create_missing_related_entities: bool = Field(
        ..., alias="createMissingRelatedEntities"
    )
    merge: bool
    resources: Optional[List[ResourceConfig]]

    class Config:
        allow_population_by_field_name = True
        validate_assignment = True
