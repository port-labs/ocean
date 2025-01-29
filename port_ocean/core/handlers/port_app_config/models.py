from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from port_ocean.clients.port.types import RequestOptions


class Rule(BaseModel):
    property: str
    operator: str
    value: str


class IngestSearchQuery(BaseModel):
    combinator: str
    rules: list[Rule | IngestSearchQuery]


class EntityMapping(BaseModel):
    identifier: str | IngestSearchQuery
    title: str | None
    blueprint: str
    team: str | None
    properties: dict[str, str] = Field(default_factory=dict)
    relations: dict[str, str | IngestSearchQuery] = Field(default_factory=dict)

    @property
    def is_using_search_identifier(self) -> bool:
        return isinstance(self.identifier, dict)


class MappingsConfig(BaseModel):
    mappings: EntityMapping


class PortResourceConfig(BaseModel):
    entity: MappingsConfig
    items_to_parse: str | None = Field(alias="itemsToParse")


class Selector(BaseModel):
    query: str


class ResourceConfig(BaseModel):
    kind: str
    selector: Selector
    port: PortResourceConfig


class PortAppConfig(BaseModel):
    enable_merge_entity: bool = Field(alias="enableMergeEntity", default=True)
    delete_dependent_entities: bool = Field(
        alias="deleteDependentEntities", default=True
    )
    create_missing_related_entities: bool = Field(
        alias="createMissingRelatedEntities", default=True
    )
    resources: list[ResourceConfig] = Field(default_factory=list)

    def get_port_request_options(self) -> RequestOptions:
        return {
            "delete_dependent_entities": self.delete_dependent_entities,
            "create_missing_related_entities": self.create_missing_related_entities,
            "merge": self.enable_merge_entity,
            "validation_only": False,
        }

    def to_request(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": self.delete_dependent_entities,
            "createMissingRelatedEntities": self.create_missing_related_entities,
            "enableMergeEntity": self.enable_merge_entity,
            "resources": [
                resource.dict(by_alias=True, exclude_none=True, exclude_unset=True)
                for resource in self.resources
            ],
        }

    class Config:
        allow_population_by_field_name = True
        validate_assignment = True
