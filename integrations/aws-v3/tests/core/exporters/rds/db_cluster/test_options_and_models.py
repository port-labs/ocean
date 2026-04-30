import pytest
from pydantic import ValidationError
from datetime import datetime

from aws.core.exporters.rds.db_cluster.models import (
    DbCluster,
    DbClusterProperties,
    SingleDbClusterRequest,
    PaginatedDbClusterRequest,
)


class TestSingleDbClusterRequest:

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = SingleDbClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            db_cluster_identifier="cluster-1",
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.db_cluster_identifier == "cluster-1"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["ListTagsForResourceAction"]
        options = SingleDbClusterRequest(
            region="eu-central-1",
            account_id="123456789012",
            db_cluster_identifier="cluster-2",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.db_cluster_identifier == "cluster-2"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        """Test validation error when region is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SingleDbClusterRequest(
                account_id="123456789012", db_cluster_identifier="cluster-1"
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_db_cluster_identifier(self) -> None:
        """Test validation error when db_cluster_identifier is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SingleDbClusterRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "db_cluster_identifier" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        """Test initialization with empty include list."""
        options = SingleDbClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            db_cluster_identifier="cluster-3",
            include=[],
        )
        assert options.include == []


class TestPaginatedDbClusterRequest:

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = PaginatedDbClusterRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        """Test initialization with optional include list."""
        include_list = ["ListTagsForResourceAction"]
        options = PaginatedDbClusterRequest(
            region="ap-southeast-2",
            account_id="123456789012",
            include=include_list,
        )
        assert options.include == include_list


class TestDbClusterProperties:

    def test_initialization_with_defaults(self) -> None:
        """Test initialization with all default values."""
        properties = DbClusterProperties()
        assert properties.DBClusterIdentifier == ""
        assert properties.DBClusterArn == ""
        assert properties.Engine == ""
        assert properties.EngineVersion == ""
        assert properties.Status == ""
        assert properties.MultiAZ is False
        assert properties.StorageEncrypted is False
        assert properties.DeletionProtection is False
        assert properties.HttpEndpointEnabled is False
        assert properties.AvailabilityZones == []
        assert properties.DBClusterMembers == []
        assert properties.Tags == []
        assert properties.VpcSecurityGroups == []

    def test_initialization_with_properties(self) -> None:
        """Test initialization with specific values."""
        properties = DbClusterProperties(
            DBClusterIdentifier="my-cluster",
            Engine="aurora-mysql",
            EngineVersion="8.0.mysql_aurora.3.04.0",
            Status="available",
            MultiAZ=True,
            StorageEncrypted=True,
            DeletionProtection=True,
            AvailabilityZones=["us-east-1a", "us-east-1b"],
            Tags=[{"Key": "Env", "Value": "prod"}],
        )
        assert properties.DBClusterIdentifier == "my-cluster"
        assert properties.Engine == "aurora-mysql"
        assert properties.Status == "available"
        assert properties.MultiAZ is True
        assert properties.StorageEncrypted is True
        assert properties.DeletionProtection is True
        assert properties.AvailabilityZones == ["us-east-1a", "us-east-1b"]
        assert properties.Tags == [{"Key": "Env", "Value": "prod"}]

    def test_all_properties_assignment(self) -> None:
        """Test assignment of all available properties."""
        properties = DbClusterProperties(
            ActivityStreamStatus="stopped",
            AssociatedRoles=[],
            AutoMinorVersionUpgrade=True,
            AvailabilityZones=["us-east-1a", "us-east-1b", "us-east-1c"],
            BackupRetentionPeriod=7,
            ClusterCreateTime=datetime(2024, 3, 15, 10, 22, 33),
            CopyTagsToSnapshot=True,
            CrossAccountClone=False,
            DatabaseName="mydb",
            DBClusterArn="arn:aws:rds:us-east-1:123456789012:cluster:my-cluster",
            DBClusterIdentifier="my-cluster",
            DBClusterMembers=[
                {"DBInstanceIdentifier": "my-cluster-1", "IsClusterWriter": True}
            ],
            DbClusterResourceId="cluster-ABC123",
            DeletionProtection=True,
            EarliestRestorableTime=datetime(2024, 3, 15, 10, 30, 0),
            Endpoint="my-cluster.cluster-abc.us-east-1.rds.amazonaws.com",
            Engine="aurora-mysql",
            EngineMode="provisioned",
            EngineVersion="8.0.mysql_aurora.3.04.0",
            GlobalWriteForwardingStatus="disabled",
            HttpEndpointEnabled=False,
            IAMDatabaseAuthenticationEnabled=True,
            KmsKeyId="arn:aws:kms:us-east-1:123456789012:key/abc123",
            LatestRestorableTime=datetime(2024, 3, 20, 8, 15, 0),
            MasterUsername="admin",
            MultiAZ=True,
            NetworkType="IPV4",
            Port=3306,
            PreferredBackupWindow="02:00-03:00",
            PreferredMaintenanceWindow="sun:05:00-sun:06:00",
            ReaderEndpoint="my-cluster.cluster-ro-abc.us-east-1.rds.amazonaws.com",
            Status="available",
            StorageEncrypted=True,
            StorageType="aurora",
            Tags=[{"Key": "Environment", "Value": "production"}],
            VpcSecurityGroups=[{"VpcSecurityGroupId": "sg-0123", "Status": "active"}],
            DBSubnetGroup="my-subnet-group",
        )

        assert properties.DBClusterIdentifier == "my-cluster"
        assert properties.Engine == "aurora-mysql"
        assert properties.EngineMode == "provisioned"
        assert properties.MultiAZ is True
        assert properties.StorageEncrypted is True
        assert properties.Port == 3306
        assert properties.AvailabilityZones == [
            "us-east-1a",
            "us-east-1b",
            "us-east-1c",
        ]
        assert len(properties.DBClusterMembers) == 1
        assert properties.Tags == [{"Key": "Environment", "Value": "production"}]

    def test_optional_fields_default_to_none(self) -> None:
        """Test that optional fields default to None."""
        properties = DbClusterProperties()
        assert properties.ActivityStreamStatus is None
        assert properties.ClusterCreateTime is None
        assert properties.DatabaseName is None
        assert properties.EarliestRestorableTime is None
        assert properties.Endpoint is None
        assert properties.EngineMode is None
        assert properties.GlobalWriteForwardingStatus is None
        assert properties.KmsKeyId is None
        assert properties.LatestRestorableTime is None
        assert properties.NetworkType is None
        assert properties.ReaderEndpoint is None
        assert properties.StorageType is None
        assert properties.DBSubnetGroup is None

    def test_extra_fields_are_ignored(self) -> None:
        """Test that unknown fields from the AWS API are silently ignored."""
        properties = DbClusterProperties(
            DBClusterIdentifier="cluster-extra",
            UnknownField="ignored",  # type: ignore[call-arg]
        )
        assert properties.DBClusterIdentifier == "cluster-extra"
        assert not hasattr(properties, "UnknownField")


class TestDbCluster:

    def test_type_is_fixed(self) -> None:
        """Test that Type is always AWS::RDS::DBCluster."""
        cluster = DbCluster(Properties=DbClusterProperties(DBClusterIdentifier="c-1"))
        assert cluster.Type == "AWS::RDS::DBCluster"

    def test_initialization_with_properties(self) -> None:
        """Test initialization with full properties."""
        properties = DbClusterProperties(
            DBClusterIdentifier="c-2",
            Engine="aurora-postgresql",
            Status="available",
            MultiAZ=True,
        )
        cluster = DbCluster(Properties=properties)
        assert cluster.Properties.DBClusterIdentifier == "c-2"
        assert cluster.Properties.Engine == "aurora-postgresql"
        assert cluster.Properties.MultiAZ is True

    def test_multiple_instances_have_independent_properties(self) -> None:
        """Test that each DbCluster instance holds its own Properties."""
        c1 = DbCluster(Properties=DbClusterProperties(DBClusterIdentifier="c-1"))
        c2 = DbCluster(Properties=DbClusterProperties(DBClusterIdentifier="c-2"))
        assert c1.Properties is not c2.Properties
        assert c1.Properties.DBClusterIdentifier == "c-1"
        assert c2.Properties.DBClusterIdentifier == "c-2"

    def test_dict_serialization(self) -> None:
        """Test dict serialization includes Type and Properties."""
        cluster = DbCluster(
            Properties=DbClusterProperties(
                DBClusterIdentifier="c-3",
                Engine="aurora-mysql",
                Status="available",
            )
        )
        data = cluster.dict(exclude_none=True)
        assert data["Type"] == "AWS::RDS::DBCluster"
        assert data["Properties"]["DBClusterIdentifier"] == "c-3"
        assert data["Properties"]["Engine"] == "aurora-mysql"
