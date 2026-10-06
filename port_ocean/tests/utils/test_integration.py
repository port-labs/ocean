from port_ocean.utils.integration import (
    read_app_spec_interval,
    resolve_app_spec_interval_minutes,
)


class TestReadAppSpecInterval:
    def test_returns_app_spec_field(self) -> None:
        integration = {"spec": {"appSpec": {"incrementalSyncInterval": "15m"}}}

        assert read_app_spec_interval(integration, "incrementalSyncInterval") == "15m"

    def test_returns_none_when_missing(self) -> None:
        assert read_app_spec_interval({}, "incrementalSyncInterval") is None


class TestResolveAppSpecIntervalMinutes:
    def test_parses_app_spec_interval(self) -> None:
        integration = {"spec": {"appSpec": {"scheduledResyncInterval": "2h"}}}

        assert (
            resolve_app_spec_interval_minutes(
                integration,
                "scheduledResyncInterval",
                fallback_minutes=15,
            )
            == 120
        )

    def test_uses_fallback_when_missing(self) -> None:
        assert (
            resolve_app_spec_interval_minutes(
                {},
                "incrementalSyncInterval",
                fallback_minutes=15,
            )
            == 15
        )
