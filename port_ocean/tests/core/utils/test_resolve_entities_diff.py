from unittest.mock import patch
from port_ocean.core.models import Entity
from port_ocean.core.utils.utils import (
    are_entities_different,
    resolve_entities_diff,
    are_entities_fields_equal,
)
from typing import Any


def create_test_entity(
    identifier: str,
    blueprint: str,
    properties: dict[str, Any],
    relations: dict[str, Any],
    title: Any,
    team: str | None | list[Any] = [],
) -> Entity:
    return Entity(
        identifier=identifier,
        blueprint=blueprint,
        properties=properties,
        relations=relations,
        title=title,
        team=team,
    )


def test_are_entities_fields_equal_identical_properties_should_be_true() -> None:
    assert (
        are_entities_fields_equal(
            {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
            {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        )
        is True
    )


def test_are_entities_fields_equal_different_number_properties_should_be_false() -> (
    None
):
    assert (
        are_entities_fields_equal(
            {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
            {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 456},
        )
        is False
    )


def test_are_entities_fields_equal_different_date_properties_should_be_false() -> None:
    assert (
        are_entities_fields_equal(
            {
                "created_at": "2024-03-20T10:00:00Z",
                "updated_at": "2024-03-21T15:30:00Z",
            },
            {
                "created_at": "2024-03-20T10:00:00Z",
                "updated_at": "2024-03-22T09:45:00Z",
            },
        )
        is False
    )


def test_are_entities_fields_equal_identical_properties_different_order_should_be_true() -> (
    None
):
    assert (
        are_entities_fields_equal(
            {"totalIssues": 123, "url": "https://test.atlassian.net/browse/test-29081"},
            {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        )
        is True
    )


def test_are_entities_fields_equal_identical_relations_should_be_true() -> None:
    assert (
        are_entities_fields_equal(
            {"reporter": "id1", "project": "project_id"},
            {"reporter": "id1", "project": "project_id"},
        )
        is True
    )


def test_are_entities_fields_equal_different_relations_should_be_false() -> None:
    assert (
        are_entities_fields_equal(
            {"reporter": "id1", "project": "project_id"},
            {"reporter": "id2", "project": "project_id"},
        )
        is False
    )


def test_are_entities_fields_equal_different_relation_keys_should_be_false() -> None:
    assert (
        are_entities_fields_equal(
            {"reporter": "id1", "project": "project_id"},
            {"assignee": "id1", "project": "project_id"},
        )
        is False
    )


def test_are_entities_fields_equal_identical_relations_different_order_should_be_true() -> (
    None
):
    assert (
        are_entities_fields_equal(
            {"project": "project_id", "reporter": "id1"},
            {"reporter": "id1", "project": "project_id"},
        )
        is True
    )


def test_are_entities_fields_equal_identical_nested_properties_should_be_true() -> None:
    assert (
        are_entities_fields_equal(
            {
                "metadata": {
                    "labels": {"env": "prod", "team": "devops"},
                    "annotations": {"description": "test"},
                },
                "spec": {"replicas": 3},
            },
            {
                "metadata": {
                    "labels": {"env": "prod", "team": "devops"},
                    "annotations": {"description": "test"},
                },
                "spec": {"replicas": 3},
            },
        )
        is True
    )


def test_are_entities_fields_equal_different_nested_properties_should_be_false() -> (
    None
):
    assert (
        are_entities_fields_equal(
            {
                "metadata": {
                    "labels": {"env": "prod", "team": "devops"},
                    "annotations": {"description": "test"},
                },
            },
            {
                "metadata": {
                    "labels": {"env": "staging", "team": "devops"},
                    "annotations": {"description": "test"},
                },
            },
        )
        is False
    )


def test_are_entities_fields_equal_identical_nested_arrays_should_be_true() -> None:
    assert (
        are_entities_fields_equal(
            {
                "containers": [
                    {"name": "app", "image": "nginx:1.14"},
                    {"name": "sidecar", "image": "proxy:2.1"},
                ],
            },
            {
                "containers": [
                    {"name": "app", "image": "nginx:1.14"},
                    {"name": "sidecar", "image": "proxy:2.1"},
                ],
            },
        )
        is True
    )


def test_are_entities_fields_equal_different_nested_arrays_should_be_false() -> None:
    assert (
        are_entities_fields_equal(
            {
                "containers": [
                    {"name": "app", "image": "nginx:1.14"},
                    {"name": "sidecar", "image": "proxy:2.1"},
                ],
            },
            {
                "containers": [
                    {"name": "app", "image": "nginx:1.15"},  # Different version
                    {"name": "sidecar", "image": "proxy:2.1"},
                ],
            },
        )
        is False
    )


def test_are_entities_fields_equal_nested_relations_should_be_true() -> None:
    assert (
        are_entities_fields_equal(
            {
                "owner": {
                    "team": "team_id1",
                    "members": ["user1", "user2"],
                    "metadata": {"role": "admin"},
                },
            },
            {
                "owner": {
                    "team": "team_id1",
                    "members": ["user1", "user2"],
                    "metadata": {"role": "admin"},
                },
            },
        )
        is True
    )


def test_are_entities_fields_equal_different_nested_relations_should_be_false() -> None:
    assert (
        are_entities_fields_equal(
            {
                "owner": {
                    "team": "team_id1",
                    "members": ["user1", "user2"],
                    "metadata": {"role": "admin"},
                },
            },
            {
                "owner": {
                    "team": "team_id1",
                    "members": ["user1", "user3"],  # Different member
                    "metadata": {"role": "admin"},
                },
            },
        )
        is False
    )


def test_are_entities_fields_equal_null_properties_should_be_true() -> None:
    assert (
        are_entities_fields_equal(
            {
                "team": None,
                "members": ["user1", "user2"],
                "metadata": {"role": "admin"},
            },
            {"members": ["user1", "user2"], "metadata": {"role": "admin"}},
        )
        is True
    )


def test_are_entities_fields_equal_null_properties_and_real_data_in_other_entity_should_be_false() -> (
    None
):
    assert (
        are_entities_fields_equal(
            {
                "team": None,
                "members": ["user1", "user2"],
                "metadata": {"role": "admin"},
            },
            {
                "team": "team_id1",
                "members": ["user1", "user2"],
                "metadata": {"role": "admin"},
            },
        )
        is False
    )


def test_are_entities_fields_equal_null_properties_in_both_should_be_true() -> None:
    assert (
        are_entities_fields_equal(
            {
                "team": None,
                "members": ["user1", "user2"],
                "metadata": {"role": "admin"},
            },
            {
                "team": None,
                "members": ["user1", "user2"],
                "metadata": {"role": "admin"},
            },
        )
        is True
    )


def test_are_entities_different_identical_entities_should_be_false() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "",
        "",
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "",
        "",
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
        "",
        "",
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "",
        "",
    )
    assert are_entities_different(entity1, entity2) is True


def test_are_entities_different_with_different_relations_should_be_true() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "",
        "",
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id2", "project": "project_id"},
        "",
        "",
    )
    assert are_entities_different(entity1, entity2) is True


def test_are_entities_different_with_different_titles_should_be_true() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "Issue 123",
        "",
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "Issue 456",
        "",
    )
    assert are_entities_different(entity1, entity2) is True


def test_are_entities_different_with_identical_titles_should_be_false() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "Issue 123",
        "",
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "Issue 123",
        "",
    )
    assert are_entities_different(entity1, entity2) is False


def test_are_entities_different_with_identical_titles_with_emoji_should_be_false() -> (
    None
):
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "🚀 Issue 123",
        "",
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "🚀 Issue 123",
        "",
    )
    assert are_entities_different(entity1, entity2) is False


def test_are_entities_different_with_different_teams_should_be_true() -> None:
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "Issue 123",
        ["team1", "team2"],
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "Issue 123",
        ["team2", "team3"],
    )
    assert are_entities_different(entity1, entity2) is True


def test_are_entities_different_with_identical_teams_different_order_should_be_false() -> (
    None
):
    entity1 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "Issue 123",
        ["team1", "team2"],
    )
    entity2 = create_test_entity(
        "",
        "",
        {"url": "https://test.atlassian.net/browse/test-29081", "totalIssues": 123},
        {"reporter": "id1", "project": "project_id"},
        "Issue 123",
        ["team2", "team1"],
    )
    assert are_entities_different(entity1, entity2) is False


entity1 = create_test_entity(
    "id1",
    "bp1",
    {"totalIssues": 123, "url": "https://test.atlassian.net/browse/test-29081"},
    {"reporter": "id1", "project": "project_id"},
    "",
    "",
)
entity1_modified_properties = create_test_entity(
    "id1",
    "bp1",
    {"totalIssues": 5, "url": "https://test.atlassian.net/browse/test-29081"},
    {"reporter": "id1", "project": "project_id"},
    "",
    "",
)
entity1_modified_relations = create_test_entity(
    "id1",
    "bp1",
    {"totalIssues": 123, "url": "https://test.atlassian.net/browse/test-29081"},
    {"reporter": "id1", "project": "project_id2"},
    "",
    "",
)
entity2 = create_test_entity(
    "id2",
    "bp2",
    {"totalIssues": 234, "url": "https://test.atlassian.net/browse/test-23451"},
    {"reporter": "id2", "project": "project_id2"},
    "",
    "",
)
entity3 = create_test_entity(
    "id3",
    "bp3",
    {"totalIssues": 20, "url": "https://test.atlassian.net/browse/test-542"},
    {"reporter": "id3", "project": "project_id3"},
    "",
    "",
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
    "",
    "",
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
    "",
    "",
)


def test_resolve_entities_diff_empty_lists() -> None:
    """Test when both input lists are empty"""
    changed = resolve_entities_diff([], [])
    assert len(changed) == 0


def test_resolve_entities_diff_new_entities() -> None:
    """Test when there are simple third party entities that are not in Port"""
    changed = resolve_entities_diff([entity1, entity2], [])
    assert len(changed) == 2
    assert changed[0] == entity1
    assert changed[1] == entity2


def test_resolve_entities_diff_deleted_entities() -> None:
    """Test when entities exist in Port but not in third party"""
    changed = resolve_entities_diff([], [entity1, entity2])
    assert len(changed) == 0


def test_resolve_entities_diff_identical_entities() -> None:
    """Test when entities are identical in both sources"""
    changed = resolve_entities_diff([entity1], [entity1])
    assert len(changed) == 0


def test_resolve_entities_diff_modified_properties() -> None:
    """Test when entities exist but have different properties"""
    changed = resolve_entities_diff([entity1_modified_properties], [entity1])
    assert len(changed) == 1
    assert changed[0] == entity1_modified_properties


def test_resolve_entities_diff_modified_relations() -> None:
    """Test when entities exist but have different relations"""
    changed = resolve_entities_diff([entity1_modified_relations], [entity1])
    assert len(changed) == 1
    assert changed[0] == entity1_modified_relations


def test_resolve_entities_diff_search_identifier_entity() -> None:
    """Test when entity uses search identifier"""
    with patch(
        "port_ocean.core.utils.utils.are_entities_different", return_value=False
    ) as mock_are_different:
        changed = resolve_entities_diff([entity_with_search_identifier], [])
        assert len(changed) == 1
        assert changed[0] == entity_with_search_identifier
        mock_are_different.assert_not_called()


def test_resolve_entities_diff_search_relation_entity() -> None:
    """Test when entity uses search relation"""
    with patch(
        "port_ocean.core.utils.utils.are_entities_different", return_value=False
    ) as mock_are_different:
        changed = resolve_entities_diff([entity_with_search_relation], [])
        assert len(changed) == 1
        assert changed[0] == entity_with_search_relation
        mock_are_different.assert_not_called()


def test_resolve_entities_diff_multiple_entities() -> None:
    """Test with multiple entities in both sources"""
    changed = resolve_entities_diff(
        [entity1_modified_properties, entity2, entity_with_search_identifier],
        [entity1, entity3],
    )
    assert len(changed) == 3
    assert changed[0] == entity1_modified_properties
    assert changed[1] == entity2
    assert changed[2] == entity_with_search_identifier
