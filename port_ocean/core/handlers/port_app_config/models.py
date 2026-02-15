from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from port_ocean.clients.port.types import RequestOptions


CUSTOM_KIND = "__custom__"


class _FieldMetadataEnforcer(BaseModel):
    """Base model that enforces all fields have 'title' and 'description' metadata.

    Any model inheriting from this class (directly or transitively) will be
    validated at class-creation time to ensure every ``Field`` includes both a
    ``title`` and a ``description``.
    """

    pass

    # TODO: Uncomment this when we completed assigning all the titles and descriptions
    # def __init_subclass__(cls, **kwargs: Any) -> None:
    #     super().__init_subclass__(**kwargs)
    #     for field_name, field in cls.__fields__.items():
    #         if field.field_info.title is None:
    #             raise TypeError(
    #                 f"Field '{field_name}' in '{cls.__name__}' must have a 'title'"
    #             )
    #         if field.field_info.description is None:
    #             raise TypeError(
    #                 f"Field '{field_name}' in '{cls.__name__}' must have a 'description'"
    #             )


class Rule(_FieldMetadataEnforcer):
    property: str = Field(title="Property", description="The property to search on.")
    operator: str = Field(
        title="Operator", description="The operator to use for the search."
    )
    value: str = Field(title="Value", description="The value to search for.")


class IngestSearchQuery(_FieldMetadataEnforcer):
    combinator: str = Field(
        title="Combinator",
        description="The combinator to use for the search, avaliable: 'and', 'or'.",
    )
    rules: list[Rule | IngestSearchQuery] = Field(
        title="Rules", description="The rules to use for the search."
    )


class EntityMapping(_FieldMetadataEnforcer):
    identifier: str | IngestSearchQuery = Field(
        title="Identifier", description="The identifier to use for the entity."
    )
    title: str | None = Field(
        title="Title", description="The title to use for the entity."
    )
    icon: str | None = Field(
        title="Icon", description="The icon to use for the entity."
    )
    blueprint: str = Field(
        title="Blueprint", description="The blueprint to use for the entity."
    )
    team: str | IngestSearchQuery | None = Field(
        title="Team", description="The team to use for the entity."
    )
    properties: dict[str, str] = Field(
        default_factory=dict,
        title="Properties",
        description="The properties to use for the entity.",
    )
    relations: dict[str, str | IngestSearchQuery] = Field(
        default_factory=dict,
        title="Relations",
        description="The relations to use for the entity.",
    )

    @property
    def is_using_search_identifier(self) -> bool:
        return isinstance(self.identifier, dict) or isinstance(
            self.identifier, IngestSearchQuery
        )


class MappingsConfig(_FieldMetadataEnforcer):
    mappings: EntityMapping = Field(
        title="Mappings", description="The mappings to use for the entity."
    )


class PortResourceConfig(_FieldMetadataEnforcer):
    entity: MappingsConfig = Field(
        title="Entity", description="The entity to use for the resource."
    )
    items_to_parse: str | None = Field(
        alias="itemsToParse",
        title="Items to Parse",
        description="JQ expression pointing on an array value in the raw data, on which multiple entities will be parsed from.",
    )
    items_to_parse_name: str = Field(
        alias="itemsToParseName",
        default="item",
        title="Items to Parse Name",
        description="The name of the key that will be enriched with the specific item context in the raw data.",
    )
    items_to_parse_top_level_transform: bool = Field(
        alias="itemsToParseTopLevelTransform",
        default=True,
        title="Items to Parse Top Level Transform",
        description="Whether to removes the target array specified in itemsToParse from the result data.",
    )


class Selector(_FieldMetadataEnforcer):
    query: str = Field(
        title="Query",
        description="JQ expression that will filter which objects of the specified kind will be ingested into Port.",
    )


class ResourceConfig(_FieldMetadataEnforcer):
    kind: str = Field(
        title="Kind",
        description="key is a specifier for the object you wish to map from the tool's API.",
    )
    selector: Selector = Field(
        title="Selector",
        description="Specifies extraction flags and transformation filters reagrding the data to ingest into Port.",
    )
    port: PortResourceConfig = Field(
        title="Port",
        description="Defines the mapping from the raw data to the entity and relations.",
    )


class PortAppConfig(_FieldMetadataEnforcer):
    enable_merge_entity: bool = Field(
        alias="enableMergeEntity",
        default=True,
        title="Enable Merge Entity",
        description="Whether to merge entities when merging an entity.",
        extra={"ui_schema": {"hidden": True}},
    )
    delete_dependent_entities: bool = Field(
        alias="deleteDependentEntities",
        default=True,
        title="Delete Dependent Entities",
        description="Flag that controls whether Port is allowed to automatically delete dependent entities when you delete a target entity that has required relations.",
    )
    create_missing_related_entities: bool = Field(
        alias="createMissingRelatedEntities",
        default=True,
        title="Create Missing Related Entities",
        description="Flag that tells Port to automatically create “placeholder” entities when they are referenced in a relation but don’t yet exist in the catalog.",
    )
    entity_deletion_threshold: float = Field(
        alias="entityDeletionThreshold",
        default=0.9,
        title="Entity Deletion Threshold",
        description="The threshold for deleting entities. If the threshold is reached, the entity will be deleted.",
    )
    resources: list[ResourceConfig] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations for the integration.",
    )

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
            "entityDeletionThreshold": self.entity_deletion_threshold,
            "resources": [
                resource.dict(by_alias=True, exclude_none=True, exclude_unset=True)
                for resource in self.resources
            ],
        }

    @classmethod
    def validate_and_get_resource_kinds(
        cls,
        allow_custom_kinds: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Validate resource kind definitions and extract their attributes."""
        from port_ocean.core.handlers.port_app_config.kind_validators import (
            validate_and_get_resource_kinds as _validate_and_get_resource_kinds,
        )

        return _validate_and_get_resource_kinds(cls, allow_custom_kinds)

    class Config:
        allow_population_by_field_name = True
        validate_assignment = True
