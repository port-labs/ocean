from typing import Any

from port_ocean.core.models import Entity
from port_ocean.core.handlers.port_app_config.models import IngestSearchQuery, Rule
from port_ocean.core.utils.entity_topological_sorter import EntityTopologicalSorter
from unittest.mock import MagicMock
from port_ocean.exceptions.core import (
    OceanAbortException,
)


def create_entity(
    identifier: Any, buleprint: str, dependencies: dict[str, Any] = {}
) -> Entity:
    entity = MagicMock()
    entity.identifier = identifier
    entity.blueprint = buleprint
    entity.relations = dependencies or {}
    return entity


def create_search_identifier(identifier: str) -> dict[str, Any]:
    return {
        "combinator": "and",
        "rules": [{"operator": "=", "property": "$identifier", "value": identifier}],
    }


def test_handle_failed_with_dependencies() -> None:
    # processed_order:list[str] = []
    entity_a = create_entity(
        "entity_a",
        "buleprint_a",
    )  # No dependencies
    entity_b = create_entity(
        "entity_b", "buleprint_a", {"dep_name_1": "entity_a"}
    )  # Depends on entity_a
    entity_c = create_entity(
        "entity_c", "buleprint_b", {"dep_name_2": "entity_b"}
    )  # Depends on entity_b

    entity_topological_sort = EntityTopologicalSorter()
    # Register fails with unsorted order
    entity_topological_sort.register_entity(entity_c)
    entity_topological_sort.register_entity(entity_a)
    entity_topological_sort.register_entity(entity_b)

    processed_order = [
        f"{entity.identifier}-{entity.blueprint}"
        for entity in list(entity_topological_sort.get_entities())
    ]
    assert processed_order == [
        "entity_a-buleprint_a",
        "entity_b-buleprint_a",
        "entity_c-buleprint_b",
    ], f"Processed order: {processed_order}"


def test_handle_failed_with_self_dependencies() -> None:
    entity_a = create_entity(
        "entity_a", "buleprint_a", {"dep_name_1": "entity_a"}
    )  # Self dependency
    entity_b = create_entity(
        "entity_b", "buleprint_a", {"dep_name_1": "entity_a"}
    )  # Depends on entity_a
    entity_c = create_entity(
        "entity_c", "buleprint_b", {"dep_name_2": "entity_b"}
    )  # Depends on entity_b

    entity_topological_sort = EntityTopologicalSorter()

    # Register fails with unsorted order
    entity_topological_sort.register_entity(entity_c)
    entity_topological_sort.register_entity(entity_a)
    entity_topological_sort.register_entity(entity_b)

    processed_order = [
        f"{entity.identifier}-{entity.blueprint}"
        for entity in list(entity_topological_sort.get_entities())
    ]

    assert processed_order == [
        "entity_a-buleprint_a",
        "entity_b-buleprint_a",
        "entity_c-buleprint_b",
    ], f"Processed order: {processed_order}"


def test_handle_failed_with_search_identifier() -> None:
    search_identifier = create_search_identifier("entity_a")
    entity_a = create_entity(
        search_identifier,
        "buleprint_a",
        {"dep_name_1": "missing_entity"},
    )

    entity_topological_sort = EntityTopologicalSorter()
    entity_topological_sort.register_entity(entity_a)

    assert list(entity_topological_sort.get_entities()) == [entity_a]


def test_handle_failed_with_search_identifier_dependencies() -> None:
    search_identifier = create_search_identifier("entity_a")
    entity_a = create_entity(search_identifier, "buleprint_a")
    entity_b = create_entity(
        "entity_b", "buleprint_b", {"dep_name_1": search_identifier}
    )

    entity_topological_sort = EntityTopologicalSorter()
    entity_topological_sort.register_entity(entity_b)
    entity_topological_sort.register_entity(entity_a)

    assert list(entity_topological_sort.get_entities()) == [entity_a, entity_b]


def test_handle_failed_with_search_relation_to_string_identifier() -> None:
    entity_a = create_entity("entity_a", "buleprint_a")
    entity_b = create_entity(
        "entity_b",
        "buleprint_b",
        {"dep_name_1": create_search_identifier("entity_a")},
    )

    entity_topological_sort = EntityTopologicalSorter()
    entity_topological_sort.register_entity(entity_b)
    entity_topological_sort.register_entity(entity_a)

    assert list(entity_topological_sort.get_entities()) == [entity_a, entity_b]


def test_handle_failed_with_pydantic_search_relation_to_string_identifier() -> None:
    entity_a = create_entity("entity_a", "buleprint_a")
    entity_b = create_entity(
        "entity_b",
        "buleprint_b",
        {
            "dep_name_1": IngestSearchQuery(
                combinator="and",
                rules=[
                    Rule(
                        operator="=",
                        property="$identifier",
                        value="entity_a",
                    )
                ],
            )
        },
    )

    entity_topological_sort = EntityTopologicalSorter()
    entity_topological_sort.register_entity(entity_b)
    entity_topological_sort.register_entity(entity_a)

    assert list(entity_topological_sort.get_entities()) == [entity_a, entity_b]


def test_handle_failed_with_mixed_relation_list_dependencies() -> None:
    entity_a = create_entity("entity_a", "buleprint_a")
    entity_b = create_entity("entity_b", "buleprint_b")
    entity_c = create_entity(
        "entity_c",
        "buleprint_c",
        {"dep_name_1": ["entity_a", create_search_identifier("entity_b")]},
    )

    entity_topological_sort = EntityTopologicalSorter()
    entity_topological_sort.register_entity(entity_c)
    entity_topological_sort.register_entity(entity_b)
    entity_topological_sort.register_entity(entity_a)

    sorted_entities = list(entity_topological_sort.get_entities())
    assert sorted_entities[-1] == entity_c
    assert {entity.identifier for entity in sorted_entities[:2]} == {
        "entity_a",
        "entity_b",
    }


def test_handle_failed_with_circular_dependencies() -> None:
    # processed_order:list[str] = []
    entity_a = create_entity(
        "entity_a", "buleprint_a", {"dep_name_1": "entity_b"}
    )  # Self dependency
    entity_b = create_entity(
        "entity_b", "buleprint_a", {"dep_name_1": "entity_a"}
    )  # Depends on entity_a

    entity_topological_sort = EntityTopologicalSorter()
    try:
        entity_topological_sort.register_entity(entity_a)
        entity_topological_sort.register_entity(entity_b)
        entity_topological_sort.get_entities()

    except OceanAbortException as e:
        assert isinstance(e, OceanAbortException)
        assert (
            e.args[0]
            == "Cannot order entities due to cyclic dependencies. \nIf you do want to have cyclic dependencies, please make sure to set the keys 'createMissingRelatedEntities' and 'deleteDependentEntities' in the integration config in Port."
        )
