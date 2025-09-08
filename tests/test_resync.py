from main import _parse_iso


def test_parse_iso():
    dt = _parse_iso("2024-01-01T00:00:00Z")
    assert dt.year == 2024
    assert dt.tzinfo is not None