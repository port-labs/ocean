import time
from typing import Generator
from unittest.mock import patch

import pytest

from gitlab.clients.rate_limiter.utils import (
    GitLabRateLimiterConfig,
    RateLimitInfo,
    RateLimiterRequiredHeaders,
    has_exhausted_rate_limit_headers,
)


class TestRateLimitInfo:
    @pytest.fixture
    def rate_limit_info(self) -> RateLimitInfo:
        """Create a RateLimitInfo with known values for testing."""
        return RateLimitInfo(
            limit=1000,
            remaining=500,
            reset_time=int(time.time()) + 60,
        )

    def test_seconds_until_reset_positive(self, rate_limit_info: RateLimitInfo) -> None:
        """Test seconds_until_reset returns positive value when reset is in future."""
        seconds = rate_limit_info.seconds_until_reset
        assert 59 <= seconds <= 60

    def test_seconds_until_reset_zero_when_past(self) -> None:
        """Test seconds_until_reset returns 0 when reset time is in the past."""
        info = RateLimitInfo(
            limit=1000,
            remaining=0,
            reset_time=int(time.time()) - 60,
        )
        assert info.seconds_until_reset == 0

    def test_utilization_percentage_half_used(
        self, rate_limit_info: RateLimitInfo
    ) -> None:
        """Test utilization_percentage when half the limit is used."""
        assert rate_limit_info.utilization_percentage == 50.0

    def test_utilization_percentage_fully_used(self) -> None:
        """Test utilization_percentage when limit is fully used."""
        info = RateLimitInfo(
            limit=1000,
            remaining=0,
            reset_time=int(time.time()) + 60,
        )
        assert info.utilization_percentage == 100.0

    def test_utilization_percentage_none_used(self) -> None:
        """Test utilization_percentage when no requests have been made."""
        info = RateLimitInfo(
            limit=1000,
            remaining=1000,
            reset_time=int(time.time()) + 60,
        )
        assert info.utilization_percentage == 0.0

    def test_utilization_percentage_zero_limit(self) -> None:
        """Test utilization_percentage handles zero limit gracefully."""
        info = RateLimitInfo(
            limit=0,
            remaining=0,
            reset_time=int(time.time()) + 60,
        )
        assert info.utilization_percentage == 0.0


class TestGitLabRateLimiterConfig:
    def test_default_max_concurrent(self) -> None:
        """Test default max_concurrent value."""
        config = GitLabRateLimiterConfig()
        assert config.max_concurrent == 10

    def test_custom_max_concurrent(self) -> None:
        """Test custom max_concurrent value."""
        config = GitLabRateLimiterConfig(max_concurrent=50)
        assert config.max_concurrent == 50


class TestRateLimiterRequiredHeaders:
    def test_parse_headers_from_dict(self) -> None:
        """Test parsing rate limit headers from dict."""
        headers = {
            "ratelimit-limit": "60",
            "ratelimit-remaining": "45",
            "ratelimit-reset": "1609459200",
        }
        parsed = RateLimiterRequiredHeaders(**headers)
        assert parsed.ratelimit_limit == "60"
        assert parsed.ratelimit_remaining == "45"
        assert parsed.ratelimit_reset == "1609459200"

    def test_parse_headers_missing_values(self) -> None:
        """Test parsing headers with missing values returns None."""
        headers = {"other-header": "value"}
        parsed = RateLimiterRequiredHeaders(**headers)
        assert parsed.ratelimit_limit is None
        assert parsed.ratelimit_remaining is None
        assert parsed.ratelimit_reset is None

    def test_parse_headers_partial_values(self) -> None:
        """Test parsing headers with partial values."""
        headers = {
            "ratelimit-remaining": "10",
        }
        parsed = RateLimiterRequiredHeaders(**headers)
        assert parsed.ratelimit_limit is None
        assert parsed.ratelimit_remaining == "10"
        assert parsed.ratelimit_reset is None


class TestHasExhaustedRateLimitHeaders:
    def test_exhausted_with_string_zero(self) -> None:
        """Test detection when remaining is string '0'."""
        headers = {
            "ratelimit-remaining": "0",
            "ratelimit-reset": "1609459200",
        }
        assert has_exhausted_rate_limit_headers(headers) is True

    def test_exhausted_with_int_zero(self) -> None:
        """Test detection when remaining is integer 0."""
        headers = {
            "ratelimit-remaining": 0,
            "ratelimit-reset": "1609459200",
        }
        assert has_exhausted_rate_limit_headers(headers) is True

    def test_not_exhausted_with_remaining(self) -> None:
        """Test returns False when remaining > 0."""
        headers = {
            "ratelimit-remaining": "10",
            "ratelimit-reset": "1609459200",
        }
        assert has_exhausted_rate_limit_headers(headers) is False

    def test_not_exhausted_without_reset(self) -> None:
        """Test returns False when reset header is missing."""
        headers = {
            "ratelimit-remaining": "0",
        }
        assert has_exhausted_rate_limit_headers(headers) is False

    def test_not_exhausted_empty_headers(self) -> None:
        """Test returns False with empty headers."""
        headers = {}
        assert has_exhausted_rate_limit_headers(headers) is False
