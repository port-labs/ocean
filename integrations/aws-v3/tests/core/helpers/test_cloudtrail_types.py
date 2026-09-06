from aws.core.helpers.metadata.types import cloudtrail_dict_value


def test_cloudtrail_dict_value_returns_dict_unchanged() -> None:
    assert cloudtrail_dict_value({"serviceArn": "arn"}) == {"serviceArn": "arn"}


def test_cloudtrail_dict_value_treats_null_as_empty() -> None:
    assert cloudtrail_dict_value(None) == {}


def test_cloudtrail_dict_value_treats_non_dict_as_empty() -> None:
    assert cloudtrail_dict_value("service") == {}
