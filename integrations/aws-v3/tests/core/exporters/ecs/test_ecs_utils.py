from aws.core.exporters.ecs.utils import (
    build_service_arn,
    is_short_service_arn,
    normalize_service_arn,
    parse_service_arn,
)


def test_is_short_service_arn() -> None:
    assert (
        is_short_service_arn("arn:aws:ecs:us-east-1:111122223333:service/my-service")
        is True
    )
    assert (
        is_short_service_arn(
            "arn:aws:ecs:us-east-1:111122223333:service/my-cluster/my-service"
        )
        is False
    )


def test_normalize_service_arn_returns_long_form_unchanged() -> None:
    service_arn = "arn:aws:ecs:us-east-1:111122223333:service/my-cluster/my-service"
    assert normalize_service_arn(service_arn) == service_arn


def test_normalize_service_arn_expands_short_form_with_cluster_arn() -> None:
    short_arn = "arn:aws:ecs:us-east-1:111122223333:service/my-service"
    cluster_arn = "arn:aws:ecs:us-east-1:111122223333:cluster/default"

    assert normalize_service_arn(short_arn, cluster_arn) == (
        "arn:aws:ecs:us-east-1:111122223333:service/default/my-service"
    )


def test_normalize_service_arn_returns_none_for_short_form_without_cluster_arn() -> (
    None
):
    short_arn = "arn:aws:ecs:us-east-1:111122223333:service/my-service"
    assert normalize_service_arn(short_arn) is None


def test_parse_service_arn_long_form() -> None:
    assert parse_service_arn(
        "arn:aws:ecs:us-east-1:111122223333:service/my-cluster/my-service"
    ) == ("my-cluster", "my-service")


def test_build_service_arn_from_bare_names() -> None:
    assert (
        build_service_arn(
            "us-east-1",
            "111122223333",
            "my-cluster",
            "my-service",
        )
        == "arn:aws:ecs:us-east-1:111122223333:service/my-cluster/my-service"
    )


def test_build_service_arn_from_cluster_arn_and_bare_service_name() -> None:
    assert (
        build_service_arn(
            "us-east-1",
            "111122223333",
            "arn:aws:ecs:us-east-1:111122223333:cluster/my-cluster",
            "my-service",
        )
        == "arn:aws:ecs:us-east-1:111122223333:service/my-cluster/my-service"
    )


def test_build_service_arn_returns_long_service_arn_unchanged() -> None:
    service_arn = "arn:aws:ecs:us-east-1:111122223333:service/my-cluster/my-service"
    assert (
        build_service_arn(
            "us-east-1",
            "111122223333",
            "my-cluster",
            service_arn,
        )
        == service_arn
    )


def test_build_service_arn_does_not_nest_service_arn_in_path() -> None:
    service_arn = "arn:aws:ecs:us-east-1:111122223333:service/my-cluster/my-service"
    assert (
        build_service_arn(
            "us-east-1",
            "111122223333",
            "arn:aws:ecs:us-east-1:111122223333:cluster/my-cluster",
            service_arn,
        )
        == service_arn
    )


def test_build_service_arn_expands_short_service_arn() -> None:
    assert (
        build_service_arn(
            "us-east-1",
            "111122223333",
            "default",
            "arn:aws:ecs:us-east-1:111122223333:service/my-service",
        )
        == "arn:aws:ecs:us-east-1:111122223333:service/default/my-service"
    )
