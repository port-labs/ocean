from datetime import UTC, datetime

from azure_integration.foundry.helpers.utils import parse_foundry_timestamp, timestamp_to_iso


def test_parse_foundry_timestamp_unix_string() -> None:
    parsed = parse_foundry_timestamp("1793724875")
    assert parsed == datetime.fromtimestamp(1793724875, tz=UTC)


def test_timestamp_to_iso_unix_string() -> None:
    iso = timestamp_to_iso("1793724875")
    assert iso == datetime.fromtimestamp(1793724875, tz=UTC).isoformat()


def test_parse_foundry_timestamp_iso_z() -> None:
    parsed = parse_foundry_timestamp("2026-01-15T12:00:00Z")
    assert parsed == datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
