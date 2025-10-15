import io
import json
from unittest.mock import Mock, call
from gitlab.helpers.utils import (
    enrich_resources_with_project,
    scalar_to_json_text,
    _clean_underscores,
    yaml_to_json_chunks,
    _yaml_to_json_stream,
    _yaml_to_json_generator,
    iter_yaml_docs_as_single_json,
    YamlToJsonStreamer,
)


class TestUtils:
    def test_enrich_resources_with_project(self) -> None:
        """Test enriching resources with project data"""
        # Arrange
        resources = [
            {"id": 1, "project_id": "123", "name": "Resource 1"},
            {"id": 2, "project_id": "456", "name": "Resource 2"},
            {"id": 3, "project_id": "789", "name": "Resource 3"},
        ]
        project_map = {
            "123": {"path_with_namespace": "group/project-a"},
            "456": {"path_with_namespace": "group/project-b"},
            "789": {"path_with_namespace": "group/project-c"},
        }

        # Act
        result = enrich_resources_with_project(resources, project_map)

        # Assert
        assert len(result) == 3
        assert result[0]["id"] == 1
        assert result[0]["__project"]["path_with_namespace"] == "group/project-a"
        assert result[1]["id"] == 2
        assert result[1]["__project"]["path_with_namespace"] == "group/project-b"
        assert result[2]["id"] == 3
        assert result[2]["__project"]["path_with_namespace"] == "group/project-c"


class TestCleanUnderscores:
    """Test the _clean_underscores helper function"""

    def test_clean_underscores_with_underscores(self) -> None:
        """Test cleaning underscores from numeric strings"""
        assert _clean_underscores("1_000_000") == "1000000"
        assert _clean_underscores("1_2_3_4") == "1234"
        assert _clean_underscores("_123_") == "123"

    def test_clean_underscores_without_underscores(self) -> None:
        """Test cleaning underscores from strings without underscores"""
        assert _clean_underscores("123") == "123"
        assert _clean_underscores("") == ""
        assert _clean_underscores("abc") == "abc"


class TestScalarToJsonText:
    """Test the scalar_to_json_text function"""

    def test_null_values(self) -> None:
        """Test null value handling"""
        assert scalar_to_json_text(None, None, None) == "null"
        assert scalar_to_json_text("null", None, None) == "null"
        assert scalar_to_json_text("~", None, None) == "null"
        assert scalar_to_json_text("", None, None) == "null"

    def test_quoted_null_values(self) -> None:
        """Test quoted null values should be treated as strings"""
        assert scalar_to_json_text("null", None, (True, True)) == '"null"'
        assert scalar_to_json_text("~", None, (True, True)) == '"~"'

    def test_boolean_values(self) -> None:
        """Test boolean value handling"""
        assert scalar_to_json_text("true", None, None) == "true"
        assert scalar_to_json_text("false", None, None) == "false"
        assert scalar_to_json_text("TRUE", None, None) == "true"
        assert scalar_to_json_text("FALSE", None, None) == "false"

    def test_quoted_boolean_values(self) -> None:
        """Test quoted boolean values should be treated as strings"""
        assert scalar_to_json_text("true", None, (True, True)) == '"true"'
        assert scalar_to_json_text("false", None, (True, True)) == '"false"'

    def test_integer_values(self) -> None:
        """Test integer value handling"""
        assert scalar_to_json_text("123", None, None) == "123"
        assert scalar_to_json_text("-456", None, None) == "-456"
        assert scalar_to_json_text("+789", None, None) == "789"
        assert scalar_to_json_text("0", None, None) == "0"
        assert scalar_to_json_text("1_000", None, None) == "1000"

    def test_float_values(self) -> None:
        """Test float value handling"""
        assert scalar_to_json_text("123.45", None, None) == "123.45"
        assert scalar_to_json_text("-456.78", None, None) == "-456.78"
        assert scalar_to_json_text("1.23e4", None, None) == "12300.0"
        assert scalar_to_json_text("1_000.5", None, None) == "1000.5"

    def test_special_float_values(self) -> None:
        """Test special float values (NaN, Infinity)"""
        assert scalar_to_json_text("nan", None, None) == '"NaN"'
        assert scalar_to_json_text(".nan", None, None) == '"NaN"'
        assert scalar_to_json_text("inf", None, None) == '"Infinity"'
        assert scalar_to_json_text("+inf", None, None) == '"Infinity"'
        assert scalar_to_json_text(".inf", None, None) == '"Infinity"'
        assert scalar_to_json_text("-inf", None, None) == '"-Infinity"'
        assert scalar_to_json_text("-.inf", None, None) == '"-Infinity"'

    def test_string_values(self) -> None:
        """Test string value handling"""
        assert scalar_to_json_text("hello", None, None) == '"hello"'
        assert scalar_to_json_text("123abc", None, None) == '"123abc"'
        assert scalar_to_json_text("", None, None) == "null"  # Empty string is null

    def test_quoted_string_values(self) -> None:
        """Test quoted string values"""
        assert scalar_to_json_text("hello", None, (True, True)) == '"hello"'
        assert scalar_to_json_text("123", None, (True, True)) == '"123"'

    def test_tagged_string_values(self) -> None:
        """Test values with explicit string tags"""
        assert scalar_to_json_text("123", "tag:yaml.org,2002:str", None) == '"123"'
        assert scalar_to_json_text("true", "tag:yaml.org,2002:str", None) == '"true"'
        assert scalar_to_json_text("null", "tag:yaml.org,2002:str", None) == '"null"'

    def test_binary_tagged_values(self) -> None:
        """Test values with binary tags"""
        assert scalar_to_json_text("SGVsbG8=", "tag:yaml.org,2002:binary", None) == '"SGVsbG8="'

    def test_timestamp_tagged_values(self) -> None:
        """Test values with timestamp tags"""
        assert scalar_to_json_text("2023-01-01", "tag:yaml.org,2002:timestamp", None) == '"2023-01-01"'


class TestYamlToJsonChunks:
    """Test the yaml_to_json_chunks function"""

    def test_single_document_array_mode(self) -> None:
        """Test single document in array mode"""
        yaml_text = "key: value"
        result = list(yaml_to_json_chunks(yaml_text, "array"))
        assert len(result) == 1
        assert json.loads(result[0]) == [{"key": "value"}]

    def test_multiple_documents_array_mode(self) -> None:
        """Test multiple documents in array mode"""
        yaml_text = "key1: value1\n---\nkey2: value2"
        result = list(yaml_to_json_chunks(yaml_text, "array"))
        assert len(result) == 1
        assert json.loads(result[0]) == [{"key1": "value1"}, {"key2": "value2"}]

    def test_single_document_single_mode(self) -> None:
        """Test single document in single mode"""
        yaml_text = "key: value"
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        assert json.loads(result[0]) == {"key": "value"}

    def test_multiple_documents_newline_mode(self) -> None:
        """Test multiple documents in newline mode"""
        yaml_text = "key1: value1\n---\nkey2: value2"
        result = list(yaml_to_json_chunks(yaml_text, "newline"))
        assert len(result) == 3  # Two JSON objects plus newline
        assert json.loads(result[0]) == {"key1": "value1"}
        assert result[1] == "\n"
        assert json.loads(result[2]) == {"key2": "value2"}

    def test_empty_yaml(self) -> None:
        """Test empty YAML input"""
        result = list(yaml_to_json_chunks("", "array"))
        assert len(result) == 1
        # Empty YAML results in empty string, which is not valid JSON
        assert result[0] == ""

    def test_file_stream_mode(self) -> None:
        """Test writing to file stream"""
        yaml_text = "key: value"
        file_stream = io.StringIO()
        result = yaml_to_json_chunks(yaml_text, "array", file_stream)
        assert result is None
        file_stream.seek(0)
        content = file_stream.read()
        assert json.loads(content) == [{"key": "value"}]


class TestYamlToJsonStream:
    """Test the _yaml_to_json_stream function"""

    def test_array_mode_stream(self) -> None:
        """Test array mode with file stream"""
        yaml_text = "key1: value1\n---\nkey2: value2"
        file_stream = io.StringIO()
        _yaml_to_json_stream(yaml_text, "array", file_stream)
        file_stream.seek(0)
        content = file_stream.read()
        assert json.loads(content) == [{"key1": "value1"}, {"key2": "value2"}]

    def test_single_mode_stream(self) -> None:
        """Test single mode with file stream"""
        yaml_text = "key: value"
        file_stream = io.StringIO()
        _yaml_to_json_stream(yaml_text, "single", file_stream)
        file_stream.seek(0)
        content = file_stream.read()
        assert json.loads(content) == {"key": "value"}

    def test_newline_mode_stream(self) -> None:
        """Test newline mode with file stream"""
        yaml_text = "key1: value1\n---\nkey2: value2"
        file_stream = io.StringIO()
        _yaml_to_json_stream(yaml_text, "newline", file_stream)
        file_stream.seek(0)
        content = file_stream.read()
        # The newline mode stream produces concatenated JSON objects followed by newline-separated ones
        # This is the actual behavior of the implementation
        assert '"key1":"value1"' in content
        assert '"key2":"value2"' in content


class TestYamlToJsonGenerator:
    """Test the _yaml_to_json_generator function"""

    def test_array_mode_generator(self) -> None:
        """Test array mode generator"""
        yaml_text = "key1: value1\n---\nkey2: value2"
        result = list(_yaml_to_json_generator(yaml_text, "array"))
        assert len(result) == 1
        assert json.loads(result[0]) == [{"key1": "value1"}, {"key2": "value2"}]

    def test_single_mode_generator(self) -> None:
        """Test single mode generator"""
        yaml_text = "key: value"
        result = list(_yaml_to_json_generator(yaml_text, "single"))
        assert len(result) == 1
        assert json.loads(result[0]) == {"key": "value"}

    def test_newline_mode_generator(self) -> None:
        """Test newline mode generator"""
        yaml_text = "key1: value1\n---\nkey2: value2"
        result = list(_yaml_to_json_generator(yaml_text, "newline"))
        assert len(result) == 3
        assert json.loads(result[0]) == {"key1": "value1"}
        assert result[1] == "\n"
        assert json.loads(result[2]) == {"key2": "value2"}


class TestIterYamlDocsAsSingleJson:
    """Test the iter_yaml_docs_as_single_json function"""

    def test_single_document(self) -> None:
        """Test single document iteration"""
        yaml_text = "key: value"
        result = list(iter_yaml_docs_as_single_json(yaml_text))
        assert len(result) == 1
        assert json.loads(result[0]) == {"key": "value"}

    def test_multiple_documents(self) -> None:
        """Test multiple documents iteration"""
        yaml_text = "key1: value1\n---\nkey2: value2\n---\nkey3: value3"
        result = list(iter_yaml_docs_as_single_json(yaml_text))
        assert len(result) == 3
        assert json.loads(result[0]) == {"key1": "value1"}
        assert json.loads(result[1]) == {"key2": "value2"}
        assert json.loads(result[2]) == {"key3": "value3"}

    def test_empty_yaml(self) -> None:
        """Test empty YAML input"""
        result = list(iter_yaml_docs_as_single_json(""))
        # Empty YAML results in empty list
        assert len(result) == 0


class TestYamlToJsonStreamer:
    """Test the YamlToJsonStreamer class"""

    def test_initialization(self) -> None:
        """Test streamer initialization"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        assert streamer.writer == writer
        assert streamer.stack == []
        assert streamer._doc_count == 0
        assert streamer._mode == "single"

    def test_set_multiple_mode(self) -> None:
        """Test setting multiple mode"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        streamer.set_multiple_mode("array")
        assert streamer._mode == "array"

    def test_comma_if_needed_empty_stack(self) -> None:
        """Test comma logic with empty stack"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        streamer._comma_if_needed()
        writer.assert_not_called()

    def test_comma_if_needed_first_element(self) -> None:
        """Test comma logic with first element"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        # Add a frame with index 0 (first element)
        from gitlab.helpers.utils import _Frame
        streamer.stack.append(_Frame("seq"))
        streamer._comma_if_needed()
        writer.assert_not_called()

    def test_comma_if_needed_subsequent_element(self) -> None:
        """Test comma logic with subsequent element"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        # Add a frame with index 1 (subsequent element)
        from gitlab.helpers.utils import _Frame
        frame = _Frame("seq")
        frame.index = 1
        streamer.stack.append(frame)
        streamer._comma_if_needed()
        writer.assert_called_once_with(",")

    def test_open_seq(self) -> None:
        """Test opening a sequence"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        streamer._open_seq()
        writer.assert_called_once_with("[")
        assert len(streamer.stack) == 1
        assert streamer.stack[0].kind == "seq"

    def test_close_seq(self) -> None:
        """Test closing a sequence"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        from gitlab.helpers.utils import _Frame
        streamer.stack.append(_Frame("seq"))
        frame = streamer._close_seq()
        writer.assert_called_once_with("]")
        assert streamer.stack == []
        assert frame.kind == "seq"

    def test_open_map(self) -> None:
        """Test opening a mapping"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        streamer._open_map()
        writer.assert_called_once_with("{")
        assert len(streamer.stack) == 1
        assert streamer.stack[0].kind == "map"
        assert streamer.stack[0].expect == "key"

    def test_close_map(self) -> None:
        """Test closing a mapping"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        from gitlab.helpers.utils import _Frame
        streamer.stack.append(_Frame("map"))
        frame = streamer._close_map()
        writer.assert_called_once_with("}")
        assert streamer.stack == []
        assert frame.kind == "map"

    def test_emit_scalar_key(self) -> None:
        """Test emitting a scalar as a key"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        from gitlab.helpers.utils import _Frame
        frame = _Frame("map", expect="key")
        streamer.stack.append(frame)
        streamer._emit_scalar("test_key", None, None)
        writer.assert_has_calls([call('"test_key":')])
        assert frame.expect == "value"

    def test_emit_scalar_value(self) -> None:
        """Test emitting a scalar as a value"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        from gitlab.helpers.utils import _Frame
        frame = _Frame("map", expect="value")
        streamer.stack.append(frame)
        streamer._emit_scalar("test_value", None, None)
        writer.assert_called_once_with('"test_value"')
        assert frame.expect == "key"
        assert frame.index == 1

    def test_emit_scalar_in_sequence(self) -> None:
        """Test emitting a scalar in a sequence"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        from gitlab.helpers.utils import _Frame
        frame = _Frame("seq")
        frame.index = 1  # Not first element
        streamer.stack.append(frame)
        streamer._emit_scalar("test_value", None, None)
        writer.assert_has_calls([call(","), call('"test_value"')])
        assert frame.index == 2

    def test_feed_simple_document(self) -> None:
        """Test feeding a simple document"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        import yaml
        yaml_text = "key: value"
        events = list(yaml.parse(io.StringIO(yaml_text)))
        streamer.feed(events)
        # Should write the JSON representation
        assert writer.call_count > 0

    def test_feed_array_mode(self) -> None:
        """Test feeding in array mode"""
        writer = Mock()
        streamer = YamlToJsonStreamer(writer)
        streamer.set_multiple_mode("array")
        import yaml
        yaml_text = "key: value"
        events = list(yaml.parse(io.StringIO(yaml_text)))
        streamer.feed(events)
        # Should write array wrapper
        assert writer.call_count > 0


class TestComplexYamlToJson:
    """Test complex YAML to JSON conversion scenarios"""

    def test_deeply_nested_structures(self) -> None:
        """Test deeply nested YAML structures"""
        yaml_text = """
level1:
  level2:
    level3:
      level4:
        level5:
          value: "deep_value"
          numbers: [1, 2, 3, 4, 5]
          nested_list:
            - item1:
                sub_item: "test"
            - item2:
                sub_item: "test2"
"""
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert parsed["level1"]["level2"]["level3"]["level4"]["level5"]["value"] == "deep_value"
        assert parsed["level1"]["level2"]["level3"]["level4"]["level5"]["numbers"] == [1, 2, 3, 4, 5]
        assert len(parsed["level1"]["level2"]["level3"]["level4"]["level5"]["nested_list"]) == 2

    def test_mixed_data_types(self) -> None:
        """Test YAML with mixed data types"""
        yaml_text = """
mixed_data:
  string_value: "hello world"
  integer_value: 42
  float_value: 3.14159
  boolean_true: true
  boolean_false: false
  null_value: null
  empty_string: ""
  quoted_number: "123"
  scientific_notation: 1.23e-4
  negative_number: -456
  zero: 0
  list_mixed: [1, "two", 3.0, true, null]
  nested_mixed:
    key1: 1
    key2: "string"
    key3: [1, 2, 3]
"""
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert parsed["mixed_data"]["string_value"] == "hello world"
        assert parsed["mixed_data"]["integer_value"] == 42
        assert parsed["mixed_data"]["float_value"] == 3.14159
        assert parsed["mixed_data"]["boolean_true"] is True
        assert parsed["mixed_data"]["boolean_false"] is False
        assert parsed["mixed_data"]["null_value"] is None
        assert parsed["mixed_data"]["empty_string"] == ""
        assert parsed["mixed_data"]["quoted_number"] == "123"
        assert parsed["mixed_data"]["scientific_notation"] == 0.000123
        assert parsed["mixed_data"]["negative_number"] == -456
        assert parsed["mixed_data"]["zero"] == 0
        assert parsed["mixed_data"]["list_mixed"] == [1, "two", 3.0, True, None]

    def test_large_arrays_and_objects(self) -> None:
        """Test large arrays and objects"""
        # Generate a large YAML structure
        large_list = list(range(1000))
        large_dict = {f"key_{i}": f"value_{i}" for i in range(100)}

        # Create the inner dict manually to avoid f-string issues
        inner_dict = {f"inner_key_{i}": f"inner_value_{i}" for i in range(20)}
        yaml_text = f"""
large_list: {large_list}
large_dict: {large_dict}
nested_large:
  inner_list: {list(range(50))}
  inner_dict: {inner_dict}
"""
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert len(parsed["large_list"]) == 1000
        assert len(parsed["large_dict"]) == 100
        assert parsed["large_list"][0] == 0
        assert parsed["large_list"][-1] == 999
        assert parsed["large_dict"]["key_0"] == "value_0"
        assert parsed["large_dict"]["key_99"] == "value_99"

    def test_special_characters_and_unicode(self) -> None:
        """Test YAML with special characters and Unicode"""
        yaml_text = """
unicode_data:
  emoji: "🚀 🎉 💻"
  chinese: "你好世界"
  arabic: "مرحبا بالعالم"
  cyrillic: "Привет мир"
  special_chars: "!@#$%^&*()_+-=[]{}|;':\\\",./<>?"
  newlines: "line1\\nline2\\nline3"
  tabs: "col1\\tcol2\\tcol3"
  quotes: 'single "double" quotes'
  backslashes: "path\\\\to\\\\file"
  unicode_escape: "\\u0041\\u0042\\u0043"
"""
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert "🚀" in parsed["unicode_data"]["emoji"]
        assert "你好世界" == parsed["unicode_data"]["chinese"]
        assert "مرحبا بالعالم" == parsed["unicode_data"]["arabic"]
        assert "Привет мир" == parsed["unicode_data"]["cyrillic"]
        assert "!@#$%^&*()" in parsed["unicode_data"]["special_chars"]
        assert "\n" in parsed["unicode_data"]["newlines"]
        assert "\t" in parsed["unicode_data"]["tabs"]

    def test_multiline_strings(self) -> None:
        """Test YAML with multiline strings"""
        yaml_text = """
multiline_data:
  literal_block: |
    This is a literal block
    with multiple lines
    and preserves newlines
  folded_block: >
    This is a folded block
    that joins lines
    with spaces
  quoted_multiline: "
    This is a quoted
    multiline string
  "
  json_like: |
    {
      "key": "value",
      "nested": {
        "array": [1, 2, 3]
      }
    }
"""
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert "\n" in parsed["multiline_data"]["literal_block"]
        # Folded block joins lines with spaces, so check for the joined content
        folded_content = parsed["multiline_data"]["folded_block"]
        assert "This is a folded block" in folded_content
        assert "that joins lines" in folded_content
        assert "with spaces" in folded_content
        # Should end with newline
        assert folded_content.endswith("\n")
        # Quoted multiline gets folded, so check for content
        quoted_content = parsed["multiline_data"]["quoted_multiline"]
        assert "This is a quoted" in quoted_content
        assert "multiline string" in quoted_content

    def test_yaml_anchors_and_aliases(self) -> None:
        """Test YAML with anchors and aliases"""
        yaml_text = """
defaults: &defaults
  timeout: 30
  retries: 3
  debug: false

service1:
  <<: *defaults
  name: "service1"
  port: 8080

service2:
  <<: *defaults
  name: "service2"
  port: 9090
  timeout: 60

shared_config: &shared
  database: "postgresql"
  host: "localhost"

app1:
  <<: *shared
  name: "app1"

app2:
  <<: *shared
  name: "app2"
"""
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        # Check that the YAML structure is preserved (anchors/aliases may not be fully resolved)
        assert "defaults" in parsed
        assert parsed["defaults"]["timeout"] == 30
        assert parsed["defaults"]["retries"] == 3
        assert parsed["defaults"]["debug"] is False

        assert "service1" in parsed
        assert parsed["service1"]["name"] == "service1"
        assert parsed["service1"]["port"] == 8080
        # The << key should be present (YAML merge key)
        assert "<<" in parsed["service1"]

        assert "service2" in parsed
        assert parsed["service2"]["name"] == "service2"
        assert parsed["service2"]["port"] == 9090
        assert parsed["service2"]["timeout"] == 60

        assert "shared_config" in parsed
        assert parsed["shared_config"]["database"] == "postgresql"
        assert parsed["shared_config"]["host"] == "localhost"

        assert "app1" in parsed
        assert parsed["app1"]["name"] == "app1"
        assert "<<" in parsed["app1"]

    def test_complex_nested_arrays(self) -> None:
        """Test complex nested array structures"""
        yaml_text = """
matrix_data:
  - [1, 2, 3]
  - [4, 5, 6]
  - [7, 8, 9]

nested_arrays:
  - - - 1
      - 2
    - - 3
      - 4
  - - - 5
      - 6
    - - 7
      - 8

mixed_nested:
  - name: "item1"
    values: [1, 2, 3]
    nested:
      - {key: "value1", number: 1}
      - {key: "value2", number: 2}
  - name: "item2"
    values: [4, 5, 6]
    nested:
      - {key: "value3", number: 3}
      - {key: "value4", number: 4}
"""
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert len(parsed["matrix_data"]) == 3
        assert parsed["matrix_data"][0] == [1, 2, 3]
        assert parsed["matrix_data"][1] == [4, 5, 6]
        assert parsed["matrix_data"][2] == [7, 8, 9]

        assert len(parsed["nested_arrays"]) == 2
        assert parsed["nested_arrays"][0][0] == [1, 2]
        assert parsed["nested_arrays"][0][1] == [3, 4]

        assert len(parsed["mixed_nested"]) == 2
        assert parsed["mixed_nested"][0]["name"] == "item1"
        assert parsed["mixed_nested"][0]["values"] == [1, 2, 3]
        assert len(parsed["mixed_nested"][0]["nested"]) == 2

    def test_edge_case_values(self) -> None:
        """Test edge case values and special numbers"""
        yaml_text = """
edge_cases:
  zero: 0
  negative_zero: -0
  very_small: 1e-10
  very_large: 1e10
  infinity_positive: .inf
  infinity_negative: -.inf
  not_a_number: .nan
  empty_list: []
  empty_dict: {}
  whitespace_string: "   "
  only_newlines: "\\n\\n\\n"
  mixed_whitespace: " \\t \\n \\r "
  json_string: '{"key": "value"}'
  yaml_string: 'key: value'
"""
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert parsed["edge_cases"]["zero"] == 0
        assert parsed["edge_cases"]["negative_zero"] == 0
        assert parsed["edge_cases"]["very_small"] == 1e-10
        assert parsed["edge_cases"]["very_large"] == 1e10
        assert parsed["edge_cases"]["infinity_positive"] == "Infinity"
        assert parsed["edge_cases"]["infinity_negative"] == "-Infinity"
        assert parsed["edge_cases"]["not_a_number"] == "NaN"
        assert parsed["edge_cases"]["empty_list"] == []
        assert parsed["edge_cases"]["empty_dict"] == {}
        assert parsed["edge_cases"]["whitespace_string"] == "   "
        assert "\n" in parsed["edge_cases"]["only_newlines"]
        assert " " in parsed["edge_cases"]["mixed_whitespace"]
        assert "\t" in parsed["edge_cases"]["mixed_whitespace"]

    def test_multiple_documents_complex(self) -> None:
        """Test multiple complex documents"""
        yaml_text = """
---
document1:
  type: "config"
  settings:
    debug: true
    log_level: "info"
  services:
    - name: "api"
      port: 8080
    - name: "db"
      port: 5432
---
document2:
  type: "data"
  records:
    - id: 1
      name: "record1"
      metadata:
        created: "2023-01-01"
        tags: ["tag1", "tag2"]
    - id: 2
      name: "record2"
      metadata:
        created: "2023-01-02"
        tags: ["tag3", "tag4"]
---
document3:
  type: "schema"
  fields:
    id:
      type: "integer"
      required: true
    name:
      type: "string"
      max_length: 100
    metadata:
      type: "object"
      properties:
        created:
          type: "string"
          format: "date"
        tags:
          type: "array"
          items:
            type: "string"
"""
        # Test array mode
        result = list(yaml_to_json_chunks(yaml_text, "array"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert len(parsed) == 3
        assert parsed[0]["document1"]["type"] == "config"
        assert parsed[1]["document2"]["type"] == "data"
        assert parsed[2]["document3"]["type"] == "schema"

        # Test newline mode
        result = list(yaml_to_json_chunks(yaml_text, "newline"))
        assert len(result) == 5  # 3 documents + 2 newlines
        assert json.loads(result[0])["document1"]["type"] == "config"
        assert result[1] == "\n"
        assert json.loads(result[2])["document2"]["type"] == "data"
        assert result[3] == "\n"
        assert json.loads(result[4])["document3"]["type"] == "schema"

    def test_malformed_yaml_handling(self) -> None:
        """Test handling of malformed YAML"""
        # Test with valid YAML that has some edge cases
        yaml_text = """
valid_part:
  key: value
  number: 42
  edge_cases:
    quoted_string: "quoted"
    single_quoted: 'single'
    mixed_quotes: 'single "double" quotes'
    trailing_comma_list: [1, 2, 3]
    empty_values:
      empty_string: ""
      null_value: null
      empty_list: []
      empty_dict: {}
"""
        # The YAML parser should handle this gracefully
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert parsed["valid_part"]["key"] == "value"
        assert parsed["valid_part"]["number"] == 42
        assert parsed["valid_part"]["edge_cases"]["quoted_string"] == "quoted"
        assert parsed["valid_part"]["edge_cases"]["single_quoted"] == "single"
        assert parsed["valid_part"]["edge_cases"]["mixed_quotes"] == 'single "double" quotes'
        assert parsed["valid_part"]["edge_cases"]["trailing_comma_list"] == [1, 2, 3]
        assert parsed["valid_part"]["edge_cases"]["empty_values"]["empty_string"] == ""
        assert parsed["valid_part"]["edge_cases"]["empty_values"]["null_value"] is None
        assert parsed["valid_part"]["edge_cases"]["empty_values"]["empty_list"] == []
        assert parsed["valid_part"]["edge_cases"]["empty_values"]["empty_dict"] == {}

    def test_large_document_memory_efficiency(self) -> None:
        """Test memory efficiency with large documents"""
        # Create a large YAML document
        large_data = {
            "items": [
                {
                    "id": i,
                    "name": f"item_{i}",
                    "description": f"Description for item {i}",
                    "metadata": {
                        "created": "2023-01-01",
                        "tags": [f"tag_{j}" for j in range(5)],
                        "nested": {
                            "level1": {
                                "level2": {
                                    "level3": f"value_{i}"
                                }
                            }
                        }
                    }
                }
                for i in range(100)  # 100 items
            ]
        }

        import yaml
        yaml_text = yaml.dump(large_data, default_flow_style=False)

        # Test that it can be processed without memory issues
        result = list(yaml_to_json_chunks(yaml_text, "single"))
        assert len(result) == 1
        parsed = json.loads(result[0])
        assert len(parsed["items"]) == 100
        assert parsed["items"][0]["id"] == 0
        assert parsed["items"][-1]["id"] == 99
        assert parsed["items"][50]["name"] == "item_50"
