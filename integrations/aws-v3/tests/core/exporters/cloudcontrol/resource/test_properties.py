import json

from aws.core.exporters.cloudcontrol.resource.properties import (
    parse_cloud_control_properties,
)


def test_parse_cloud_control_properties_from_json_string() -> None:
    parsed = parse_cloud_control_properties('{"RoleName": "admin", "Path": "/"}')
    assert parsed == {"RoleName": "admin", "Path": "/"}


def test_parse_cloud_control_properties_from_dict() -> None:
    payload = {"RoleName": "admin"}
    assert parse_cloud_control_properties(payload) is payload


def test_parse_cloud_control_properties_empty_and_invalid() -> None:
    assert parse_cloud_control_properties(None) == {}
    assert parse_cloud_control_properties("") == {}
    assert parse_cloud_control_properties("[]") == {}
    assert parse_cloud_control_properties("{not-json") == {}
    assert parse_cloud_control_properties(json.dumps(["not", "an", "object"])) == {}
