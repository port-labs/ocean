"""Unit tests for probe serialization."""

from dataclasses import asdict
from datetime import datetime, timezone

from port_ocean.core.probe.models import ProbeCheck, ProbeCheckStatus
from port_ocean.core.probe.serialization import serialize_probe_value


def test_serialize_probe_check_serializes_enums() -> None:
    check = ProbeCheck(
        kind="repository",
        scopes={"org": "acme", "repo_id": 42},
        status=ProbeCheckStatus.SUCCESS,
        message="ok",
    )

    assert serialize_probe_value(asdict(check)) == {
        "kind": "repository",
        "scopes": {"org": "acme", "repo_id": 42},
        "status": "SUCCESS",
        "message": "ok",
    }


def test_serialize_probe_value_serializes_datetimes() -> None:
    # Arrange
    timestamp = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)

    # Act
    serialized = serialize_probe_value(
        {
            "startedAt": timestamp,
            "endedAt": None,
            "checks": [],
        }
    )

    # Assert
    assert serialized == {
        "startedAt": "2026-08-30T12:00:00+00:00",
        "endedAt": None,
        "checks": [],
    }
