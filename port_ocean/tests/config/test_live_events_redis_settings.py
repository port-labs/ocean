import pytest
from pydantic.v1 import ValidationError

from port_ocean.config.settings import LiveEventsRedisSettings


class TestLiveEventsRedisSettingsValidation:
    def test_accepts_redis_url_without_tls(self) -> None:
        settings = LiveEventsRedisSettings(url="redis://localhost:6379")

        assert settings.enable_tls is False
        assert settings.pel_requeue_worker_enabled is True

    def test_pel_requeue_worker_enabled_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from port_ocean.config.settings import IntegrationConfiguration

        monkeypatch.setenv(
            "OCEAN__LIVE_EVENTS__REDIS__PEL_REQUEUE_WORKER_ENABLED", "true"
        )
        monkeypatch.setenv("OCEAN__PORT__CLIENT_ID", "test-client-id")
        monkeypatch.setenv("OCEAN__PORT__CLIENT_SECRET", "test-client-secret")
        monkeypatch.setenv("OCEAN__INTEGRATION__TYPE", "test")
        monkeypatch.setenv("OCEAN__INTEGRATION__IDENTIFIER", "test-id")

        config = IntegrationConfiguration()

        assert config.live_events.redis.pel_requeue_worker_enabled is True

    def test_accepts_rediss_url_with_tls_enabled(self) -> None:
        settings = LiveEventsRedisSettings(
            url="rediss://localhost:6379",
            enable_tls=True,
        )

        assert settings.enable_tls is True

    def test_rejects_rediss_url_without_tls_enabled(self) -> None:
        with pytest.raises(ValidationError, match="enable_tls is False"):
            LiveEventsRedisSettings(url="rediss://localhost:6379")

    def test_rejects_tls_enabled_with_redis_url(self) -> None:
        with pytest.raises(ValidationError, match="rediss://"):
            LiveEventsRedisSettings(
                url="redis://localhost:6379",
                enable_tls=True,
            )

    def test_accepts_mutual_tls_when_cert_and_private_key_are_set(self) -> None:
        settings = LiveEventsRedisSettings(
            url="rediss://localhost:6379",
            enable_tls=True,
            cert="Y2VydA==",
            private_key="a2V5",
        )

        assert settings.cert == "Y2VydA=="
        assert settings.private_key == "a2V5"

    def test_rejects_cert_without_private_key(self) -> None:
        with pytest.raises(ValidationError, match="cert and private_key"):
            LiveEventsRedisSettings(
                url="rediss://localhost:6379",
                enable_tls=True,
                cert="Y2VydA==",
            )

    def test_rejects_private_key_without_cert(self) -> None:
        with pytest.raises(ValidationError, match="cert and private_key"):
            LiveEventsRedisSettings(
                url="rediss://localhost:6379",
                enable_tls=True,
                private_key="a2V5",
            )
