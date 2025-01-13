from port_ocean.core.models import Entity
from port_ocean.core.utils.utils import map_entities, are_entities_equal


def create_test_entity(identifier: str, blueprint: str, properties: dict) -> Entity:
    return Entity(identifier=identifier, blueprint=blueprint, properties=properties)


def test_are_entities_equal():
    # Test case 1: Identical entities
    entity1 = create_test_entity("id1", "bp1", {"name": "test", "value": 123})
    entity2 = create_test_entity("id1", "bp1", {"name": "test", "value": 123})
    assert are_entities_equal(entity1, entity2) is True

    # Test case 2: Same identifier, same blueprint, different properties
    entity3 = create_test_entity("id1", "bp1", {"name": "test", "value": 456})
    assert are_entities_equal(entity1, entity3) is False

    # Test case 3: Same identifier, same blueprint, same properties in different order
    entity4 = create_test_entity("id1", "bp1", {"value": 123, "name": "test"})
    assert are_entities_equal(entity1, entity4) is True

    # Test case 4: Same identifier, same blueprint, nested properties in different order
    entity5 = create_test_entity("id1", "bp1", {"nested": {"a": 1, "b": 2}})
    entity6 = create_test_entity("id1", "bp1", {"nested": {"b": 2, "a": 1}})
    assert are_entities_equal(entity5, entity6) is True

    # Test case 5: Same identifier, different blueprint, same properties
    entity7 = create_test_entity("id1", "bp1", {"name": "test"})
    entity8 = create_test_entity("id1", "bp2", {"name": "test"})
    assert are_entities_equal(entity7, entity8) is False

    # Test case 6: Different identifier, same blueprint, same properties
    entity9 = create_test_entity("id1", "bp1", {"name": "test"})
    entity10 = create_test_entity("id2", "bp1", {"name": "test"})
    assert are_entities_equal(entity9, entity10) is False

    # Test case 7: map by property identifier -> different identifier, same blueprint, same properties
    search_identifier1 = {
        "combinator": "and",
        "rules": [
            {"operator": "=", "property": "pagerduty_service_id", "value": "pd123"}
        ],
    }

    entity11 = create_test_entity(
        str(search_identifier1), "bp1", {"name": "test", "value": 123}
    )
    assert are_entities_equal(entity11, entity1) is False

    # Test case 8: map by property identifier ->  identifier mapped to the same identifier, same blueprint, same properties
    entity13 = create_test_entity("pd123", "bp1", {"name": "test", "value": 123})
    assert are_entities_equal(entity11, entity13) is False


def test_map_entities():
    # Create test entities
    third_party_entities = [
        create_test_entity("id1", "bp1", {"name": "test1"}),
        create_test_entity("id2", "bp1", {"name": "test2"}),
        create_test_entity("id3", "bp1", {"name": "test3_modified"}),
    ]

    port_entities = [
        create_test_entity("id1", "bp1", {"name": "test1"}),
        create_test_entity("id3", "bp1", {"name": "test3"}),
        create_test_entity("id4", "bp1", {"name": "test4"}),
    ]

    unique_entities, unrelevant_entities = map_entities(
        third_party_entities, port_entities
    )

    # Test unique entities (to be upserted)
    assert len(unique_entities) == 2
    assert any(e.identifier == "id2" for e in unique_entities)  # New entity
    assert any(e.identifier == "id3" for e in unique_entities)  # Modified entity

    # Test unrelevant entities (to be deleted)
    assert len(unrelevant_entities) == 1
    assert unrelevant_entities[0].identifier == "id4"


def test_map_entities_empty_lists():
    # Test with empty lists
    unique_entities, unrelevant_entities = map_entities([], [])
    assert len(unique_entities) == 0
    assert len(unrelevant_entities) == 0

    # Test with empty third party entities
    port_entities = [create_test_entity("id1", "bp1", {"name": "test1"})]
    unique_entities, unrelevant_entities = map_entities([], port_entities)
    assert len(unique_entities) == 0
    assert len(unrelevant_entities) == 1

    # Test with empty port entities
    third_party_entities = [create_test_entity("id1", "bp1", {"name": "test1"})]
    unique_entities, unrelevant_entities = map_entities(third_party_entities, [])
    assert len(unique_entities) == 1
    assert len(unrelevant_entities) == 0


def test_map_entities_different_blueprints():
    # Test entities with same identifier but different blueprints
    third_party_entities = [
        create_test_entity("id1", "bp1", {"name": "test1"}),
        create_test_entity("id1", "bp2", {"name": "test1"}),
    ]

    port_entities = [
        create_test_entity("id1", "bp1", {"name": "test1"}),
    ]

    unique_entities, unrelevant_entities = map_entities(
        third_party_entities, port_entities
    )
    assert len(unique_entities) == 1
    assert unique_entities[0].blueprint == "bp2"
    assert len(unrelevant_entities) == 0
