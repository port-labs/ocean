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
    spec_path: Optional[str | List[str]] = Field(alias="specPath", default=None)
    branch: Optional[str] = "main"
    enable_merge_entity: Optional[bool] = Field(alias="enableMergeEntity", default=None)
    delete_dependent_entities: Optional[bool] = Field(
        alias="deleteDependentEntities", default=None
    )
    create_missing_related_entities: Optional[bool] = Field(
        alias="createMissingRelatedEntities", default=None
    )
    merge: Optional[bool] = True
    resources: List[ResourceConfig] = Field(default_factory=list)

    class Config:
        allow_population_by_field_name = True
        validate_assignment = True
