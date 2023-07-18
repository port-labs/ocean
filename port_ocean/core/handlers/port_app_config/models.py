from typing import Optional, Any

from pydantic import BaseModel, Field

from port_ocean.clients.port.types import RequestOptions


class EntityMapping(BaseModel):
    identifier: str
    title: str | None
    blueprint: str
    properties: dict[str, str] = Field(default_factory=dict)
    relations: dict[str, str] = Field(default_factory=dict)


class PortResourceConfig(BaseModel):
    class MappingsConfig(BaseModel):
        mappings: EntityMapping

    entity: Optional[MappingsConfig]


class ResourceConfig(BaseModel):
    class Selector(BaseModel):
        query: str

    kind: str
    selector: Selector
    port: PortResourceConfig


class PortAppConfig(BaseModel):
    enable_merge_entity: bool = Field(alias="enableMergeEntity", default=False)
    delete_dependent_entities: bool = Field(
        alias="deleteDependentEntities", default=False
    )
    create_missing_related_entities: bool = Field(
        alias="createMissingRelatedEntities", default=False
    )
    resources: list[ResourceConfig] = Field(default_factory=list)

    def get_port_request_options(self) -> RequestOptions:
        return {
            "delete_dependent_entities": self.delete_dependent_entities,
            "create_missing_related_entities": self.create_missing_related_entities,
            "merge": self.enable_merge_entity,
        }

    def to_request(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": self.delete_dependent_entities,
            "createMissingRelatedEntities": self.create_missing_related_entities,
            "enableMergeEntity": self.enable_merge_entity,
            "resources": [resource.dict(by_alias=True) for resource in self.resources],
        }

    class Config:
        allow_population_by_field_name = True
        validate_assignment = True
