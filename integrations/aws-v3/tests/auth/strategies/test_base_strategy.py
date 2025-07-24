import pytest
from aws.auth.strategies.base import HealthCheckMixin
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider


class TestAWSSessionStrategyBase:
    """Test the base AWSSessionStrategy class."""

    def test_strategy_initialization(self) -> None:
        """Test AWSSessionStrategy initialization."""
        provider = StaticCredentialProvider()
        config = {"test_key": "test_value"}
        strategy = SingleAccountStrategy(provider=provider, config=config)
        assert strategy.provider == provider
        assert strategy.config == config


class TestHealthCheckMixin:
    """Test HealthCheckMixin functionality."""

    @pytest.mark.asyncio
    async def test_healthcheck_mixin_interface(self) -> None:
        """Test that HealthCheckMixin provides the required interface."""
        assert hasattr(HealthCheckMixin, "healthcheck")
        assert callable(HealthCheckMixin.healthcheck)
