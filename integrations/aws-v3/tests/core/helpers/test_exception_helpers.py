from botocore.exceptions import ClientError

from aws.core.helpers.utils import (
    is_access_denied_exception,
    is_cloud_control_type_unavailable_exception,
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


def test_is_resource_not_found_exception_includes_rds_codes() -> None:
    assert is_resource_not_found_exception(_client_error("DBInstanceNotFound")) is True
    assert (
        is_resource_not_found_exception(_client_error("DBClusterNotFoundFault")) is True
    )


def test_is_resource_not_found_exception_includes_ec2_and_elasticache_codes() -> None:
    assert (
        is_resource_not_found_exception(_client_error("InvalidInstanceID.NotFound"))
        is True
    )
    assert (
        is_resource_not_found_exception(_client_error("InvalidVolume.NotFound")) is True
    )
    assert (
        is_resource_not_found_exception(_client_error("CacheClusterNotFoundFault"))
        is True
    )


def test_is_resource_not_found_exception_includes_ecr_and_cluster_codes() -> None:
    assert (
        is_resource_not_found_exception(_client_error("RepositoryNotFoundException"))
        is True
    )
    assert (
        is_resource_not_found_exception(_client_error("ClusterNotFoundException"))
        is True
    )


def test_is_resource_not_found_exception_includes_ecs_codes() -> None:
    assert (
        is_resource_not_found_exception(_client_error("ServiceNotFoundException"))
        is True
    )
    assert (
        is_resource_not_found_exception(
            _client_error("TaskDefinitionNotFoundException")
        )
        is True
    )


def test_is_resource_not_found_exception_includes_sqs_codes() -> None:
    assert (
        is_resource_not_found_exception(
            _client_error("AWS.SimpleQueueService.NonExistentQueue")
        )
        is True
    )


def test_is_resource_not_found_exception_includes_cicd_and_memorydb_codes() -> None:
    assert (
        is_resource_not_found_exception(_client_error("PipelineNotFoundException"))
        is True
    )
    assert (
        is_resource_not_found_exception(
            _client_error("PipelineExecutionNotFoundException")
        )
        is True
    )
    assert (
        is_resource_not_found_exception(
            _client_error("DeploymentDoesNotExistException")
        )
        is True
    )
    assert is_resource_not_found_exception(_client_error("UserNotFoundFault")) is True


def test_is_access_denied_exception() -> None:
    assert is_access_denied_exception(_client_error("AccessDenied")) is True
    assert is_access_denied_exception(_client_error("NoSuchBucket")) is False


def test_is_access_denied_exception_unwraps_general_service_exception() -> None:
    error = ClientError(
        {
            "Error": {
                "Code": "GeneralServiceException",
                "Message": "Handler returned AccessDenied for this resource",
            }
        },
        "GetResource",
    )

    assert is_access_denied_exception(error) is True


def test_is_resource_not_found_exception_unwraps_general_service_exception() -> None:
    error = ClientError(
        {
            "Error": {
                "Code": "GeneralServiceException",
                "Message": "The requested resource does not exist",
            }
        },
        "GetResource",
    )

    assert is_resource_not_found_exception(error) is True


def test_is_cloud_control_type_unavailable_exception() -> None:
    assert (
        is_cloud_control_type_unavailable_exception(
            _client_error("TypeNotFoundException")
        )
        is True
    )
    assert (
        is_cloud_control_type_unavailable_exception(
            _client_error("UnsupportedActionException")
        )
        is True
    )
    assert (
        is_cloud_control_type_unavailable_exception(
            _client_error("CFNRegistryException")
        )
        is True
    )
    assert (
        is_cloud_control_type_unavailable_exception(_client_error("AccessDenied"))
        is False
    )
    assert (
        is_cloud_control_type_unavailable_exception(
            ClientError(
                {
                    "Error": {
                        "Code": "GeneralServiceException",
                        "Message": "The resource type is not available in this region",
                    }
                },
                "ListResources",
            )
        )
        is True
    )
