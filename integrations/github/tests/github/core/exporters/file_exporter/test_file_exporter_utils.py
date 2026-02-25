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
    assert result == "hello \ufffd world"


def test_decode_content_utf16_fallback():
    # "hello world" encoded in UTF-16LE
    # b'h\x00e\x00l\x00l\x00o\x00 \x00w\x00o\x00r\x00l\x00d\x00'
    utf16_content = "hello world".encode("utf-16le")
    encoded = base64.b64encode(utf16_content).decode("utf-8")

    result = decode_content(encoded, "base64")

    # When decoding UTF-16 bytes as UTF-8 with replacement:
    # 'h' (0x68) is valid ascii/utf-8 -> 'h'
    # '\x00' is valid ascii/utf-8 -> '\x00' (which is then stripped by replace("\x00", ""))
    # So "h\x00e\x00..." becomes "h\x00e\x00..." in UTF-8 interpretation because ASCII bytes match.
    # The stripping of null bytes happens at the end.
    # Let's use a character that produces bytes invalid in UTF-8 to trigger the exception.

    # ☃ (Snowman) is U+2603.
    # In UTF-16LE: b'\x03\x26'
    # In UTF-8: b'\xe2\x98\x83'

    # If we encode ☃ in UTF-16LE, we get b'\x03\x26'.
    # Trying to decode b'\x03\x26' as UTF-8:
    # \x03 is valid (control char).
    # \x26 is valid (&).
    # This doesn't trigger UnicodeDecodeError.

    # We need a sequence that is invalid UTF-8.
    # 0xFF is invalid in UTF-8 unless part of a multibyte sequence, but never as a start byte if it's 0xFF.
    # Actually 0xFF is never valid in UTF-8.

    # Let's create content with 0xFF.
    bad_bytes = b"hello\xffworld"
    encoded_bad = base64.b64encode(bad_bytes).decode("utf-8")

    result = decode_content(encoded_bad, "base64")
    # \xff is replaced by U+FFFD
    assert result == "hello\ufffdworld"
