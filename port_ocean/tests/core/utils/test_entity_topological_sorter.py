from port_ocean.core.models import Entity
from port_ocean.core.utils.entity_topological_sorter import EntityTopologicalSorter
from unittest.mock import MagicMock
from port_ocean.exceptions.core import (
    OceanAbortException,
)


def create_entity(
    identifier: str, buleprint: str, dependencies: dict[str, str] = {}
) -> Entity:
    entity = MagicMock()
    entity.identifier = identifier
    entity.blueprint = buleprint
    entity.relations = dependencies or {}
    return entity


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
