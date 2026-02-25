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


def test_decode_content_fallback_invalid_utf8():
    # Construct invalid UTF-8 bytes: b'\x80' is a continuation byte without a start byte
    invalid_utf8 = b"hello \x80 world"
    encoded = base64.b64encode(invalid_utf8).decode("utf-8")

    result = decode_content(encoded, "base64")

    # The invalid byte should be replaced by the replacement character  (U+FFFD)
    # Depending on implementation it might be replaced by space or question mark,
    # but python's errors="replace" usually uses U+FFFD.
    assert result == "hello  world"
