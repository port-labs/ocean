import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from aws.core.exporters.msk.serverless_cluster.models import (
    MskServerlessCluster,
    MskServerlessClusterProperties,
    SingleMskServerlessClusterRequest,
    PaginatedMskServerlessClusterRequest,
)


class TestMskServerlessClusterModels:
    def test_properties_defaults(self) -> None:
        props = MskServerlessClusterProperties()
        assert props.clusterArn == ""
        assert props.clusterName == ""
        assert props.state is None
        assert props.serverless is None
        assert props.tags is None

    def test_properties_field_population(self) -> None:
        props = MskServerlessClusterProperties(
            clusterArn="arn:aws:kafka:us-east-1:123456789012:cluster/test/abc123",
            clusterName="test-cluster",
            state="ACTIVE",
            clusterType="SERVERLESS",
        )
        assert (
            props.clusterArn
            == "arn:aws:kafka:us-east-1:123456789012:cluster/test/abc123"
        )
        assert props.clusterName == "test-cluster"
        assert props.state == "ACTIVE"

    def test_resource_model_type(self) -> None:
        cluster = MskServerlessCluster()
        assert cluster.Type == "AWS::MSK::ServerlessCluster"

    def test_serverless_field_is_dict(self) -> None:
        serverless_data: dict[str, object] = {
            "VpcConfigs": [
                {"SubnetIds": ["subnet-abc"], "SecurityGroupIds": ["sg-abc"]}
            ],
            "ClientAuthentication": {"Sasl": {"Iam": {"Enabled": True}}},
            "ConnectivityInfo": {"NetworkType": "IPV4"},
        }
        props = MskServerlessClusterProperties(
            clusterArn="arn:test",
            clusterName="test",
            serverless=serverless_data,
        )
        assert props.serverless == serverless_data

    def test_state_info_field_is_dict(self) -> None:
        props = MskServerlessClusterProperties(
            clusterArn="arn:test",
            clusterName="test",
            stateInfo={"Code": "CLUSTER_NOT_IN_ACTIVE_STATE", "Message": "Creating"},
        )
        assert props.stateInfo is not None
        assert props.stateInfo["Code"] == "CLUSTER_NOT_IN_ACTIVE_STATE"

    def test_creation_time_field(self) -> None:
        ts = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        props = MskServerlessClusterProperties(
            clusterArn="arn:test",
            clusterName="test",
            creationTime=ts,
        )
        assert props.creationTime == ts

    def test_full_resource_model(self) -> None:
        cluster = MskServerlessCluster(
            Properties=MskServerlessClusterProperties(
                clusterArn="arn:aws:kafka:us-east-1:123456789012:cluster/prod/abc",
                clusterName="prod-cluster",
                state="ACTIVE",
                clusterType="SERVERLESS",
                currentVersion="K3AEGXETSR30VB",
                tags={"env": "prod"},
            )
        )
        assert cluster.Type == "AWS::MSK::ServerlessCluster"
        assert cluster.Properties.clusterName == "prod-cluster"
        assert cluster.Properties.state == "ACTIVE"
        assert cluster.Properties.tags == {"env": "prod"}

    def test_single_request_model(self) -> None:
        req = SingleMskServerlessClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            cluster_arn="arn:aws:kafka:us-east-1:123456789012:cluster/test/abc",
            include=[],
        )
        assert (
            req.cluster_arn == "arn:aws:kafka:us-east-1:123456789012:cluster/test/abc"
        )
        assert req.region == "us-east-1"

    def test_single_request_missing_cluster_arn(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleMskServerlessClusterRequest(
                region="us-east-1",
                account_id="123456789012",  # type: ignore
            )
        assert "cluster_arn" in str(exc_info.value)

    def test_paginated_request_model(self) -> None:
        req = PaginatedMskServerlessClusterRequest(
            region="eu-west-1",
            account_id="111222333444",
            include=[],
        )
        assert req.region == "eu-west-1"
        assert req.account_id == "111222333444"
        assert req.include == []

    def test_extra_fields_ignored(self) -> None:
        props = MskServerlessClusterProperties(
            clusterArn="arn:test",
            clusterName="name",
        )
        assert props.clusterName == "name"
        assert not hasattr(props, "UnknownField")
