from typing import List, Optional, Dict, TypeVar, Union, Generic

from pydantic import BaseModel, Field


class EntityMapping(BaseModel):
    identifier: str
    title: str
    blueprint: str
    properties: Dict[str, str] = Field(default_factory=dict)
    relations: Dict[str, str] = Field(default_factory=dict)


class BlueprintMapping(BaseModel):
    identifier: str
    title: str
    properties: Dict[str, str] = Field(default_factory=dict)
    relations: Dict[str, str] = Field(default_factory=dict)


MappingType = TypeVar("MappingType", bound=Union[EntityMapping, BlueprintMapping])


class PortResourceConfig(BaseModel):
    class MappingsConfig(BaseModel, Generic[MappingType]):
        mappings: MappingType

    entity: Optional[MappingsConfig[EntityMapping]]
    blueprint: Optional[MappingsConfig[BlueprintMapping]]


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
    resources: List[ResourceConfig] = Field(default_factory=list)

    class Config:
        allow_population_by_field_name = True
        validate_assignment = True
