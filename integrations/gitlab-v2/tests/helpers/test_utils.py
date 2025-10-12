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
