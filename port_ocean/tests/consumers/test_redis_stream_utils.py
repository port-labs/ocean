import pytest
from redis.exceptions import ResponseError

from port_ocean.consumers.redis_stream_utils import is_missing_stream_or_group_error


class TestIsMissingStreamOrGroupError:
    @pytest.mark.parametrize(
        "message",
        [
            "NOGROUP No such key 'stream' or consumer group 'group'",
            "nogroup consumer group name does not exist",
        ],
    )
    def test_returns_true_for_missing_stream_or_group(self, message: str) -> None:
        assert is_missing_stream_or_group_error(ResponseError(message)) is True

    def test_returns_false_for_other_response_errors(self) -> None:
        assert (
            is_missing_stream_or_group_error(ResponseError("BUSYGROUP already exists"))
            is False
        )

    def test_returns_false_for_non_response_errors(self) -> None:
        assert is_missing_stream_or_group_error(RuntimeError("boom")) is False
