import pytest
from pydantic import ValidationError

from aws.core.exporters.cloudcontrol.resource.models import (
    CloudControlResource,
    CloudControlResourceProperties,
    PaginatedCloudControlResourceRequest,
    SingleCloudControlResourceRequest,
)
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.modeling.resource_models import ExtraContextModel


class TestCloudControlResourceRequests:
    def test_single_request_requires_type_and_identifier(self) -> None:
        request = SingleCloudControlResourceRequest(
            region="us-east-1",
            account_id="123456789012",
            type_name="AWS::IAM::Role",
            identifier="admin-role",
        )
        assert request.type_name == "AWS::IAM::Role"
        assert request.identifier == "admin-role"
        assert request.include == []

    def test_single_request_missing_identifier(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleCloudControlResourceRequest(
                region="us-east-1",
                account_id="123456789012",
                type_name="AWS::IAM::Role",
            )  # type: ignore[call-arg]
        assert "identifier" in str(exc_info.value)

    def test_paginated_request_defaults(self) -> None:
        request = PaginatedCloudControlResourceRequest(
            region="us-east-1",
            account_id="123456789012",
            type_name="AWS::IAM::Role",
        )
        assert request.use_get_resource_api is False
        assert request.resource_scope == "auto"


class TestCloudControlResourceModel:
    def test_extra_cloud_control_properties_are_preserved(self) -> None:
        resource = CloudControlResource(
            Type="AWS::IAM::Role",
            Properties=CloudControlResourceProperties.model_validate(
                {
                    "Identifier": "admin-role",
                    "RoleName": "admin-role",
                    "Path": "/",
                    "Arn": "arn:aws:iam::123456789012:role/admin-role",
                }
            ),
            ExtraContext=ExtraContextModel(
                AccountId="123456789012", Region="us-east-1"
            ),
        )
        dumped = resource.model_dump(mode="json", by_alias=True)
        assert dumped["Type"] == "AWS::IAM::Role"
        assert dumped["Properties"]["Identifier"] == "admin-role"
        assert dumped["Properties"]["RoleName"] == "admin-role"
        assert dumped["Properties"]["Path"] == "/"
        assert dumped["__ExtraContext"]["AccountId"] == "123456789012"

    def test_resource_builder_sets_dynamic_type(self) -> None:
        built = (
            ResourceBuilder(CloudControlResource)
            .with_type("AWS::IAM::Role")
            .with_properties({"Identifier": "role-1", "RoleName": "role-1"})
            .with_extra_context({"AccountId": "123", "Region": "eu-west-1"})
            .build()
        )
        assert built["Type"] == "AWS::IAM::Role"
        assert built["Properties"]["RoleName"] == "role-1"
        assert built["__ExtraContext"]["Region"] == "eu-west-1"
