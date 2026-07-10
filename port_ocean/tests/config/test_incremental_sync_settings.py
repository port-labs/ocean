import pytest

from port_ocean.config.settings import IntegrationSettings
from port_ocean.utils.time import parse_interval_to_minutes


class TestParseIntervalToMinutes:
    @pytest.mark.parametrize(
        ("raw", "expected_minutes"),
        [
            (15, 15),
            ("15", 15),
            ("15m", 15),
            ("1h", 60),
            ("2h", 120),
        ],
    )
    def test_parses_interval_to_minutes(
        self, raw: int | str, expected_minutes: int
    ) -> None:
        assert parse_interval_to_minutes(raw) == expected_minutes

    def test_defaults_to_15_minutes_for_empty_string(self) -> None:
        assert parse_interval_to_minutes("") == 15

    def test_rejects_invalid_interval_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid format"):
            parse_interval_to_minutes("not-an-interval")


class TestIncrementalSyncIntervalParsing:
    def test_settings_use_parse_interval_to_minutes(self) -> None:
        settings = IntegrationSettings(
            identifier="test",
            type="github",
            incremental_sync_interval="30m",
        )

        assert settings.incremental_sync_interval == 30

    def test_defaults_to_15_minutes(self) -> None:
        settings = IntegrationSettings(identifier="test", type="github")

        assert settings.incremental_sync_interval == 15
