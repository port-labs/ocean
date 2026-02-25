import base64
import pytest
from github.core.exporters.file_exporter.utils import decode_content

def test_decode_content_removes_null_bytes():
    # "hello\x00world" encoded in base64
    original_content = b"hello\x00world"
    encoded = base64.b64encode(original_content).decode("utf-8")

    result = decode_content(encoded, "base64")

    assert result == "helloworld"
    assert "\x00" not in result

def test_decode_content_normal_string():
    original_content = b"hello world"
    encoded = base64.b64encode(original_content).decode("utf-8")

    result = decode_content(encoded, "base64")

    assert result == "hello world"

def test_decode_content_invalid_encoding():
    with pytest.raises(ValueError, match="Unsupported encoding"):
        decode_content("content", "utf-8")
