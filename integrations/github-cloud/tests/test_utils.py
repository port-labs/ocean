import pytest
from github_cloud.helpers.utils import ObjectKind, parse_file_content

def test_object_kind_enum():
    assert ObjectKind.REPOSITORY == "repository"
    assert ObjectKind.PULL_REQUEST == "pull-request"
    assert ObjectKind.ISSUE == "issue"
    assert ObjectKind.TEAM_WITH_MEMBERS == "team-with-members"
    assert ObjectKind.MEMBER == "member"

def test_parse_file_content_empty():
    content = ""
    result = parse_file_content(content, "test.txt", "test-context")
    assert result == ""

def test_parse_file_content_whitespace():
    content = "   \n   \t   "
    result = parse_file_content(content, "test.txt", "test-context")
    assert result == "   \n   \t   "

def test_parse_file_content_json():
    content = '{"name": "test", "value": 123}'
    result = parse_file_content(content, "test.json", "test-context")
    assert result == {"name": "test", "value": 123}

def test_parse_file_content_json_array():
    content = '[1, 2, 3, {"name": "test"}]'
    result = parse_file_content(content, "test.json", "test-context")
    assert result == [1, 2, 3, {"name": "test"}]

def test_parse_file_content_yaml():
    content = """
    name: test
    value: 123
    items:
      - item1
      - item2
    """
    result = parse_file_content(content, "test.yaml", "test-context")
    assert result == {
        "name": "test",
        "value": 123,
        "items": ["item1", "item2"]
    }

def test_parse_file_content_yaml_multiple_documents():
    content = """---
name: doc1
---
name: doc2"""
    result = parse_file_content(content, "test.yaml", "test-context")
    assert result == [
        {"name": "doc1"},
        {"name": "doc2"}
    ]

def test_parse_file_content_yaml_empty_document():
    content = """---
---"""
    result = parse_file_content(content, "test.yaml", "test-context")
    assert result == content

def test_parse_file_content_invalid_json_and_yaml():
    content = "this is not json or yaml"
    result = parse_file_content(content, "test.txt", "test-context")
    assert result == content

def test_parse_file_content_complex_yaml():
    content = """
    name: test
    nested:
      key1: value1
      key2:
        - item1
        - item2
      key3:
        subkey1: subvalue1
        subkey2: subvalue2
    """
    result = parse_file_content(content, "test.yaml", "test-context")
    assert result == {
        "name": "test",
        "nested": {
            "key1": "value1",
            "key2": ["item1", "item2"],
            "key3": {
                "subkey1": "subvalue1",
                "subkey2": "subvalue2"
            }
        }
    }

def test_parse_file_content_json_with_comments():
    content = """
    {
        // This is a comment
        "name": "test",
        /* This is another comment */
        "value": 123
    }
    """
    result = parse_file_content(content, "test.json", "test-context")
    assert result == content
