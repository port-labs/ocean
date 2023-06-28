from typing import Optional

from pydantic import BaseModel, Field

from port_ocean.clients.port.types import RequestOptions


class EntityMapping(BaseModel):
    identifier: str
    title: str
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

    class Config:
        allow_population_by_field_name = True
        validate_assignment = True
