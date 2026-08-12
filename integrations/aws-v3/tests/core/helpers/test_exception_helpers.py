from botocore.exceptions import ClientError

from aws.core.helpers.utils import (
    is_access_denied_exception,
    is_resource_not_found_exception,
)


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "Op")


def test_is_resource_not_found_exception_includes_s3_codes() -> None:
    assert is_resource_not_found_exception(_client_error("NoSuchBucket")) is True
    assert is_resource_not_found_exception(_client_error("404")) is True
    assert (
        is_resource_not_found_exception(_client_error("ResourceNotFoundException"))
        is True
    )
    assert is_resource_not_found_exception(_client_error("AccessDenied")) is False


def test_is_access_denied_exception() -> None:
    assert is_access_denied_exception(_client_error("AccessDenied")) is True
    assert is_access_denied_exception(_client_error("NoSuchBucket")) is False
