import pytest
from pydantic import ValidationError
from datetime import datetime, timezone

from aws.core.exporters.eks.cluster.models import (
    EksCluster,
    EksClusterProperties,
    SingleEksClusterRequest,
    PaginatedEksClusterRequest,
)


class TestExporterOptions:
    """Test the base ExporterOptions class."""

    def test_single_eks_cluster_request_initialization_with_required_fields(
        self,
    ) -> None:
        """Test initialization with only required fields."""
        options = SingleEksClusterRequest(
            region="us-west-2", account_id="123456789012", cluster_name="test-cluster"
        )

        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.cluster_name == "test-cluster"
        assert options.include == []  # Default empty list

    def test_single_eks_cluster_request_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["DescribeClusterAction"]
        options = SingleEksClusterRequest(
            region="eu-central-1",
            account_id="123456789012",
            cluster_name="test-cluster",
            include=include_list,
        )

        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.cluster_name == "test-cluster"
        assert options.include == include_list

    def test_single_eks_cluster_request_missing_required_region(self) -> None:
        """Test that missing region raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleEksClusterRequest(
                cluster_name="test-cluster", account_id="123456789012"  # type: ignore
            )

        assert "region" in str(exc_info.value)

    def test_single_eks_cluster_request_missing_required_cluster_name(self) -> None:
        """Test that missing cluster_name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleEksClusterRequest(
                region="us-west-2", account_id="123456789012"  # type: ignore
            )

        assert "cluster_name" in str(exc_info.value)

    def test_paginated_eks_cluster_request_initialization(self) -> None:
        """Test initialization of paginated request."""
        options = PaginatedEksClusterRequest(
            region="us-west-2", account_id="123456789012"
        )

        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.include == []  # Default empty list

    def test_paginated_eks_cluster_request_with_include(self) -> None:
        """Test paginated request with include list."""
        include_list = ["DescribeClusterAction"]
        options = PaginatedEksClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            include=include_list,
        )

        assert options.include == include_list


class TestEksClusterModels:
    def test_eks_cluster_properties_cloudformation_mapping(self) -> None:
        """Test that CloudFormation fields are properly mapped."""
        properties = EksClusterProperties(
            name="test-cluster",
            version="1.28",
            roleArn="arn:aws:iam::123456789012:role/EKSClusterRole",
            resourcesVpcConfig={
                "subnetIds": ["subnet-12345", "subnet-67890"],
                "securityGroupIds": ["sg-12345"],
                "endpointPrivateAccess": True,
                "endpointPublicAccess": True,
            },
            logging={
                "clusterLogging": [
                    {"enabled": True, "types": ["api", "audit", "authenticator"]}
                ]
            },
            tags={"Environment": "test", "Project": "eks"},
        )

        assert properties.name == "test-cluster"
        assert properties.version == "1.28"
        assert properties.roleArn == "arn:aws:iam::123456789012:role/EKSClusterRole"
        assert properties.resourcesVpcConfig is not None
        assert properties.resourcesVpcConfig["subnetIds"] == [
            "subnet-12345",
            "subnet-67890",
        ]
        assert properties.tags == {"Environment": "test", "Project": "eks"}

    def test_eks_cluster_properties_api_mapping(self) -> None:
        """Test that API-only fields are properly mapped."""
        properties = EksClusterProperties(
            arn="arn:aws:eks:us-west-2:123456789012:cluster/test-cluster",
            status="ACTIVE",
            endpoint="https://ABC123DEF4567890.gr7.us-west-2.eks.amazonaws.com",
            platformVersion="eks.5",
            createdAt=datetime.fromtimestamp(1640995200, tz=timezone.utc),
        )

        assert (
            properties.arn == "arn:aws:eks:us-west-2:123456789012:cluster/test-cluster"
        )
        assert properties.status == "ACTIVE"
        assert (
            properties.endpoint
            == "https://ABC123DEF4567890.gr7.us-west-2.eks.amazonaws.com"
        )
        assert properties.platformVersion == "eks.5"

        expected_datetime = datetime.fromtimestamp(1640995200, tz=timezone.utc)
        assert properties.createdAt == expected_datetime

    def test_eks_cluster_resource_model(self) -> None:
        """Test the complete EKS cluster resource model."""
        cluster = EksCluster(
            Properties=EksClusterProperties(
                name="production-cluster",
                version="1.28",
                roleArn="arn:aws:iam::123456789012:role/EKSClusterRole",
                arn="arn:aws:eks:us-west-2:123456789012:cluster/production-cluster",
                status="ACTIVE",
            ),
        )

        assert cluster.Type == "AWS::EKS::Cluster"
        assert cluster.Properties.name == "production-cluster"
        assert cluster.Properties.version == "1.28"
        assert cluster.Properties.status == "ACTIVE"

    def test_single_eks_cluster_request(self) -> None:
        """Test single cluster request model."""
        request = SingleEksClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_name="test-cluster",
            include=[],
        )

        assert request.cluster_name == "test-cluster"
        assert request.region == "us-west-2"
        assert request.account_id == "123456789012"

    def test_paginated_eks_cluster_request(self) -> None:
        """Test paginated cluster request model."""
        request = PaginatedEksClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            include=[],
        )

        assert request.region == "us-west-2"
        assert request.account_id == "123456789012"

    def test_eks_cluster_all_properties_example(self) -> None:
        """Test example with all available EKS cluster properties."""
        from datetime import datetime

        properties = EksClusterProperties(
            # Required fields
            arn="arn:aws:eks:us-west-2:123456789012:cluster/test-cluster",
            name="test-cluster",
            version="1.28",
            roleArn="arn:aws:iam::123456789012:role/EKSClusterRole",
            status="ACTIVE",
            # Optional fields
            accessConfig={"authenticationMode": "API"},
            certificateAuthority={"data": "LS0tLS1CRUdJTi..."},
            computeConfig={"enabled": True, "nodePools": ["general-purpose"]},
            createdAt=datetime(2024, 1, 1, 12, 0, 0),
            endpoint="https://ABC123DEF4567890.gr7.us-west-2.eks.amazonaws.com",
            identity={
                "oidc": {"issuer": "https://oidc.eks.us-west-2.amazonaws.com/id/ABC123"}
            },
            kubernetesNetworkConfig={
                "serviceIpv4Cidr": "172.20.0.0/16",
                "ipFamily": "ipv4",
            },
            logging={"clusterLogging": [{"enabled": True, "types": ["api", "audit"]}]},
            platformVersion="eks.5",
            resourcesVpcConfig={
                "subnetIds": ["subnet-12345", "subnet-67890"],
                "securityGroupIds": ["sg-12345"],
                "endpointPrivateAccess": True,
                "endpointPublicAccess": True,
            },
            storageConfig={"blockStorage": {"enabled": True}},
            tags={"Environment": "test", "Project": "eks"},
            upgradePolicy={"supportType": "STANDARD"},
            zonalShiftConfig={"enabled": True},
        )

        # Verify all properties are set correctly
        assert (
            properties.arn == "arn:aws:eks:us-west-2:123456789012:cluster/test-cluster"
        )
        assert properties.name == "test-cluster"
        assert properties.version == "1.28"
        assert properties.roleArn == "arn:aws:iam::123456789012:role/EKSClusterRole"
        assert properties.status == "ACTIVE"
        assert properties.accessConfig is not None
        assert properties.accessConfig["authenticationMode"] == "API"
        assert properties.certificateAuthority is not None
        assert properties.certificateAuthority["data"] == "LS0tLS1CRUdJTi..."
        assert properties.computeConfig is not None
        assert properties.computeConfig["enabled"] is True
        assert properties.createdAt == datetime(2024, 1, 1, 12, 0, 0)
        assert (
            properties.endpoint
            == "https://ABC123DEF4567890.gr7.us-west-2.eks.amazonaws.com"
        )
        assert properties.identity is not None
        assert (
            properties.identity["oidc"]["issuer"]
            == "https://oidc.eks.us-west-2.amazonaws.com/id/ABC123"
        )
        assert properties.kubernetesNetworkConfig is not None
        assert properties.kubernetesNetworkConfig["serviceIpv4Cidr"] == "172.20.0.0/16"
        assert properties.logging is not None
        assert properties.logging["clusterLogging"][0]["enabled"] is True
        assert properties.platformVersion == "eks.5"
        assert properties.resourcesVpcConfig is not None
        assert properties.resourcesVpcConfig["subnetIds"] == [
            "subnet-12345",
            "subnet-67890",
        ]
        assert properties.storageConfig is not None
        assert properties.storageConfig["blockStorage"]["enabled"] is True
        assert properties.tags == {"Environment": "test", "Project": "eks"}
        assert properties.upgradePolicy is not None
        assert properties.upgradePolicy["supportType"] == "STANDARD"
        assert properties.zonalShiftConfig is not None
        assert properties.zonalShiftConfig["enabled"] is True
