from typing import Any

from port_ocean.core.models import Entity
from port_ocean.core.utils.utils import get_port_diff


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


def test_get_port_diff_with_dictionary_identifier() -> None:
    """
    Test that get_port_diff handles dictionary identifiers by converting them to strings.
    An entity with a dictionary identifier in 'before' and not in 'after' should be marked as deleted.
    """
    entity_with_dict_id = create_test_entity(
        identifier={"rules": "some_id", "combinator": "some combinator"},  # type: ignore
        blueprint="bp1",
        properties={},
        relations={},
        title="test",
    )
    before = [entity_with_dict_id]
    after: list[Entity] = []

    diff = get_port_diff(before, after)

    assert not diff.created
    assert not diff.modified
    assert len(diff.deleted) == 1
    assert entity_with_dict_id in diff.deleted


def test_get_port_diff_no_changes() -> None:
    """
    Test get_port_diff with no changes between before and after.
    Entities present in both should be in the 'modified' list.
    """
    before = [entity1, entity2]
    after = [entity1, entity2]

    diff = get_port_diff(before, after)

    assert not diff.created
    assert not diff.deleted
    assert len(diff.modified) == 2
    assert entity1 in diff.modified
    assert entity2 in diff.modified


def test_get_port_diff_created_entities() -> None:
    """
    Test get_port_diff with only new entities.
    """
    before: list[Entity] = []
    after = [entity1, entity2]

    diff = get_port_diff(before, after)

    assert not diff.modified
    assert not diff.deleted
    assert len(diff.created) == 2
    assert entity1 in diff.created
    assert entity2 in diff.created


def test_get_port_diff_deleted_entities() -> None:
    """
    Test get_port_diff with only deleted entities.
    """
    before = [entity1, entity2]
    after: list[Entity] = []

    diff = get_port_diff(before, after)

    assert not diff.created
    assert not diff.modified
    assert len(diff.deleted) == 2
    assert entity1 in diff.deleted
    assert entity2 in diff.deleted


def test_get_port_diff_modified_entities() -> None:
    """
    Test get_port_diff with modified entities.
    Entities with same identifier and blueprint are considered modified.
    """
    before = [entity1, entity2]
    after = [entity1_modified_properties, entity2]

    diff = get_port_diff(before, after)

    assert not diff.created
    assert not diff.deleted
    assert len(diff.modified) == 2
    assert entity1_modified_properties in diff.modified
    assert entity2 in diff.modified


def test_get_port_diff_mixed_changes() -> None:
    """
    Test get_port_diff with a mix of created, modified, and deleted entities.
    """
    before = [entity1, entity2]
    after = [entity1_modified_properties, entity3]

    diff = get_port_diff(before, after)

    assert len(diff.created) == 1
    assert entity3 in diff.created

    assert len(diff.modified) == 1
    assert entity1_modified_properties in diff.modified

    assert len(diff.deleted) == 1
    assert entity2 in diff.deleted
