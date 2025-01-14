from unittest.mock import patch
from port_ocean.core.models import Entity
from port_ocean.core.utils.utils import (
    are_entities_different,
    are_entities_relations_equal,
    map_entities,
    are_entities_properties_equal,
)
from typing import Any


def create_test_entity(
    identifier: str,
    blueprint: str,
    properties: dict[str, Any],
    relations: dict[str, Any],
) -> Entity:
    return Entity(
        identifier=identifier,
        blueprint=blueprint,
        properties=properties,
        relations=relations,
    )


def test_are_entities_properties_equal_identical_properties_should_be_true() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {},
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {},
    )
    assert are_entities_properties_equal(entity1, entity2) is True


def test_are_entities_properties_equal_different_number_properties_should_be_false() -> (
    None
):
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {},
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 456},
        {},
    )
    assert are_entities_properties_equal(entity1, entity2) is False


def test_are_entities_properties_equal_different_date_properties_should_be_false() -> (
    None
):
    entity1 = create_test_entity(
        "",
        "",
        {"created_at": "2024-03-20T10:00:00Z", "updated_at": "2024-03-21T15:30:00Z"},
        {},
    )
    entity2 = create_test_entity(
        "",
        "",
        {"created_at": "2024-03-20T10:00:00Z", "updated_at": "2024-03-22T09:45:00Z"},
        {},
    )
    assert are_entities_properties_equal(entity1, entity2) is False


def test_are_entities_properties_equal_identical_properties_different_order_should_be_true() -> (
    None
):
    entity1 = create_test_entity(
        "",
        "",
        {"totalIssues": 123, "url": "https://test.atlassian.net/browse/test-29081"},
        {},
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {},
    )
    assert are_entities_properties_equal(entity1, entity2) is True


def test_are_entities_relations_equal_identical_relations_should_be_true() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {},
        {"reporter": "id1", "project": "project_id"},
    )
    entity2 = create_test_entity(
        "",
        "",
        {},
        {"reporter": "id1", "project": "project_id"},
    )
    assert are_entities_relations_equal(entity1, entity2) is True


def test_are_entities_relations_equal_different_relations_should_be_false() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {},
        {"reporter": "id1", "project": "project_id"},
    )
    entity2 = create_test_entity(
        "",
        "",
        {},
        {"reporter": "id2", "project": "project_id"},
    )
    assert are_entities_relations_equal(entity1, entity2) is False


def test_are_entities_relations_equal_different_relation_keys_should_be_false() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {},
        {"reporter": "id1", "project": "project_id"},
    )
    entity2 = create_test_entity(
        "",
        "",
        {},
        {"assignee": "id1", "project": "project_id"},
    )
    assert are_entities_relations_equal(entity1, entity2) is False


def test_are_entities_relations_equal_identical_relations_different_order_should_be_true() -> (
    None
):
    entity1 = create_test_entity(
        "",
        "",
        {},
        {"project": "project_id", "reporter": "id1"},
    )
    entity2 = create_test_entity(
        "",
        "",
        {},
        {"reporter": "id1", "project": "project_id"},
    )
    assert are_entities_relations_equal(entity1, entity2) is True


def test_are_entities_different_identical_entities_should_be_false() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
    )
    assert are_entities_different(entity1, entity2) is False


def test_are_entities_different_entities_with_different_properties_should_be_true() -> (
    None
):
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 10},
        {"reporter": "id1", "project": "project_id"},
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
    )
    assert are_entities_different(entity1, entity2) is True


def test_are_entities_different_with_different_relations_should_be_true() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id2", "project": "project_id"},
    )
    assert are_entities_different(entity1, entity2) is True


entity1 = create_test_entity(
    "id1",
    "bp1",
    {"totalIssues": 123, "url": "https://test.atlassian.net/browse/test-29081"},
    {"reporter": "id1", "project": "project_id"},
)
entity1_modified_properties = create_test_entity(
    "id1",
    "bp1",
    {"totalIssues": 5, "url": "https://test.atlassian.net/browse/test-29081"},
    {"reporter": "id1", "project": "project_id"},
)
entity1_modified_relations = create_test_entity(
    "id1",
    "bp1",
    {"totalIssues": 123, "url": "https://test.atlassian.net/browse/test-29081"},
    {"reporter": "id1", "project": "project_id2"},
)
entity2 = create_test_entity(
    "id2",
    "bp2",
    {"totalIssues": 234, "url": "https://test.atlassian.net/browse/test-23451"},
    {"reporter": "id2", "project": "project_id2"},
)
entity3 = create_test_entity(
    "id3",
    "bp3",
    {"totalIssues": 20, "url": "https://test.atlassian.net/browse/test-542"},
    {"reporter": "id3", "project": "project_id3"},
)
entity_with_search_identifier = create_test_entity(
    str(
        {
            "combinator": "and",
            "rules": [
                {"property": "github_username", "operator": "=", "value": "name"}
            ],
        }
    ),
    "bp3",
    {"totalIssues": 234, "url": "https://test.atlassian.net/browse/test-23451"},
    {"reporter": "id2", "project": "project_id2"},
)
entity_with_search_relation = create_test_entity(
    "id4",
    "bp4",
    {"totalIssues": 234, "url": "https://test.atlassian.net/browse/test-23451"},
    {
        "reporter": "id2",
        "service_owner": {
            "combinator": "and",
            "rules": [
                {"property": "github_username", "operator": "=", "value": "name"}
            ],
        },
    },
)


def test_map_entities_empty_lists() -> None:
    """Test when both input lists are empty"""
    changed, unrelevant = map_entities([], [])
    assert len(changed) == 0
    assert len(unrelevant) == 0


def test_map_entities_new_entities() -> None:
    """Test when there are simple third party entities that are not in Port"""
    changed, unrelevant = map_entities([entity1, entity2], [])
    assert len(changed) == 2
    assert changed[0] == entity1
    assert changed[1] == entity2
    assert len(unrelevant) == 0


def test_map_entities_deleted_entities() -> None:
    """Test when entities exist in Port but not in third party"""
    changed, unrelevant = map_entities([], [entity1, entity2])
    assert len(changed) == 0
    assert len(unrelevant) == 2
    assert unrelevant[0] == entity1
    assert unrelevant[1] == entity2


def test_map_entities_identical_entities() -> None:
    """Test when entities are identical in both sources"""
    changed, unrelevant = map_entities([entity1], [entity1])
    assert len(changed) == 0
    assert len(unrelevant) == 0


def test_map_entities_modified_properties() -> None:
    """Test when entities exist but have different properties"""
    changed, unrelevant = map_entities([entity1_modified_properties], [entity1])
    assert len(changed) == 1
    assert changed[0] == entity1_modified_properties
    assert len(unrelevant) == 0


def test_map_entities_modified_relations() -> None:
    """Test when entities exist but have different relations"""
    changed, unrelevant = map_entities([entity1_modified_relations], [entity1])
    assert len(changed) == 1
    assert changed[0] == entity1_modified_relations
    assert len(unrelevant) == 0


def test_map_entities_search_identifier_entity() -> None:
    """Test when entity uses search identifier"""
    with patch(
        "port_ocean.core.utils.utils.are_entities_different", return_value=False
    ) as mock_are_different:
        changed, unrelevant = map_entities([entity_with_search_identifier], [])
        assert len(changed) == 1
        assert changed[0] == entity_with_search_identifier
        assert len(unrelevant) == 0
        mock_are_different.assert_not_called()


def test_map_entities_search_relation_entity() -> None:
    """Test when entity uses search relation"""
    with patch(
        "port_ocean.core.utils.utils.are_entities_different", return_value=False
    ) as mock_are_different:
        changed, unrelevant = map_entities([entity_with_search_relation], [])
        assert len(changed) == 1
        assert changed[0] == entity_with_search_relation
        assert len(unrelevant) == 0
        mock_are_different.assert_not_called()


def test_map_entities_multiple_entities() -> None:
    """Test with multiple entities in both sources"""
    changed, unrelevant = map_entities(
        [entity1_modified_properties, entity2, entity_with_search_identifier],
        [entity1, entity3],
    )
    assert len(changed) == 3
    assert len(unrelevant) == 1
    assert changed[0] == entity1_modified_properties
    assert changed[1] == entity2
    assert changed[2] == entity_with_search_identifier
    assert unrelevant[0] == entity3
