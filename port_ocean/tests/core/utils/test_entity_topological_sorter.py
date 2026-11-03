from typing import Any
from unittest.mock import MagicMock

import pytest

from port_ocean.core.handlers.port_app_config.models import IngestSearchQuery, Rule
from port_ocean.core.models import Entity
from port_ocean.core.utils.entity_topological_sorter import (
    order_by_entities_dependencies,
)
from port_ocean.exceptions.core import OceanAbortException


def create_entity(
    identifier: Any, blueprint: str, dependencies: dict[str, Any] | None = None
) -> Entity:
    entity = MagicMock()
    entity.identifier = identifier
    entity.blueprint = blueprint
    entity.relations = dependencies or {}
    return entity


def create_search_identifier(identifier: str) -> dict[str, Any]:
    return {
        "combinator": "and",
        "rules": [{"operator": "=", "property": "$identifier", "value": identifier}],
    }


def _keys(entities: list[Entity]) -> list[str]:
    return [f"{entity.identifier}-{entity.blueprint}" for entity in entities]


def test_orders_by_dependencies() -> None:
    entity_a = create_entity("entity_a", "blueprint_a")
    entity_b = create_entity("entity_b", "blueprint_a", {"dep_name_1": "entity_a"})
    entity_c = create_entity("entity_c", "blueprint_b", {"dep_name_2": "entity_b"})

    ordered = order_by_entities_dependencies([entity_c, entity_a, entity_b])

    assert _keys(ordered) == [
        "entity_a-blueprint_a",
        "entity_b-blueprint_a",
        "entity_c-blueprint_b",
    ]


def test_ignores_self_dependencies() -> None:
    entity_a = create_entity("entity_a", "blueprint_a", {"dep_name_1": "entity_a"})
    entity_b = create_entity("entity_b", "blueprint_a", {"dep_name_1": "entity_a"})
    entity_c = create_entity("entity_c", "blueprint_b", {"dep_name_2": "entity_b"})

    ordered = order_by_entities_dependencies([entity_c, entity_a, entity_b])

    assert _keys(ordered) == [
        "entity_a-blueprint_a",
        "entity_b-blueprint_a",
        "entity_c-blueprint_b",
    ]


def test_search_identifier_with_missing_dependency() -> None:
    entity_a = create_entity(
        create_search_identifier("entity_a"),
        "blueprint_a",
        {"dep_name_1": "missing_entity"},
    )

    assert order_by_entities_dependencies([entity_a]) == [entity_a]


def test_search_identifier_dependencies() -> None:
    search_identifier = create_search_identifier("entity_a")
    entity_a = create_entity(search_identifier, "blueprint_a")
    entity_b = create_entity(
        "entity_b", "blueprint_b", {"dep_name_1": search_identifier}
    )

    assert order_by_entities_dependencies([entity_b, entity_a]) == [entity_a, entity_b]


def test_search_relation_to_string_identifier() -> None:
    entity_a = create_entity("entity_a", "blueprint_a")
    entity_b = create_entity(
        "entity_b",
        "blueprint_b",
        {"dep_name_1": create_search_identifier("entity_a")},
    )

    assert order_by_entities_dependencies([entity_b, entity_a]) == [entity_a, entity_b]


def test_pydantic_search_relation_to_string_identifier() -> None:
    entity_a = create_entity("entity_a", "blueprint_a")
    entity_b = create_entity(
        "entity_b",
        "blueprint_b",
        {
            "dep_name_1": IngestSearchQuery(
                combinator="and",
                rules=[Rule(operator="=", property="$identifier", value="entity_a")],
            )
        },
    )

    assert order_by_entities_dependencies([entity_b, entity_a]) == [entity_a, entity_b]


def test_mixed_relation_list_dependencies() -> None:
    entity_a = create_entity("entity_a", "blueprint_a")
    entity_b = create_entity("entity_b", "blueprint_b")
    entity_c = create_entity(
        "entity_c",
        "blueprint_c",
        {"dep_name_1": ["entity_a", create_search_identifier("entity_b")]},
    )

    ordered = order_by_entities_dependencies([entity_c, entity_b, entity_a])

    assert ordered[-1] == entity_c
    assert {entity.identifier for entity in ordered[:2]} == {"entity_a", "entity_b"}


def test_circular_dependencies_raise() -> None:
    entity_a = create_entity("entity_a", "blueprint_a", {"dep_name_1": "entity_b"})
    entity_b = create_entity("entity_b", "blueprint_a", {"dep_name_1": "entity_a"})

    with pytest.raises(OceanAbortException, match="cyclic dependencies"):
        order_by_entities_dependencies([entity_a, entity_b])
