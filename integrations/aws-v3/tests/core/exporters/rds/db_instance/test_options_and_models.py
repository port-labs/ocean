import pytest
from pydantic import ValidationError
from datetime import datetime

from aws.core.exporters.rds.db_instance.models import (
    DbInstance,
    DbInstanceProperties,
    SingleDbInstanceRequest,
    PaginatedDbInstanceRequest,
)


class TestSingleDbInstanceRequest:

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = SingleDbInstanceRequest(
            region="us-west-2", account_id="123456789012", db_instance_identifier="db-1"
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.db_instance_identifier == "db-1"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["ListTagsForResourceAction"]
        options = SingleDbInstanceRequest(
            region="eu-central-1",
            account_id="123456789012",
            db_instance_identifier="db-2",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.db_instance_identifier == "db-2"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        """Test validation error when region is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SingleDbInstanceRequest(
                account_id="123456789012", db_instance_identifier="db-1"
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_db_instance_identifier(self) -> None:
        """Test validation error when db_instance_identifier is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SingleDbInstanceRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "db_instance_identifier" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        """Test initialization with empty include list."""
        options = SingleDbInstanceRequest(
            region="us-east-1",
            account_id="123456789012",
            db_instance_identifier="db-3",
            include=[],
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        """Test include list with multiple actions."""
        options = SingleDbInstanceRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            db_instance_identifier="db-3",
            include=["ListTagsForResourceAction", "DescribeDBInstancesAction"],
        )
        assert len(options.include) == 2
        assert "ListTagsForResourceAction" in options.include
        assert "DescribeDBInstancesAction" in options.include


class TestPaginatedDbInstanceRequest:

    def test_inheritance(self) -> None:
        """Test that PaginatedDbInstanceRequest inherits properly."""
        options = PaginatedDbInstanceRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedDbInstanceRequest)

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = PaginatedDbInstanceRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        """Test initialization with include actions."""
        include_list = ["ListTagsForResourceAction"]
        options = PaginatedDbInstanceRequest(
            region="ap-southeast-2", account_id="123456789012", include=include_list
        )
        assert options.region == "ap-southeast-2"
        assert options.account_id == "123456789012"
        assert options.include == include_list


class TestDbInstanceProperties:

    def test_initialization_empty(self) -> None:
        """Test initialization with default values."""
        properties = DbInstanceProperties()
        assert properties.DBInstanceIdentifier == ""
        assert properties.DBInstanceArn == ""
        assert properties.Engine == ""
        assert properties.DBInstanceClass == ""
        assert properties.DBInstanceStatus == ""
        assert properties.MultiAZ is False
        assert properties.StorageEncrypted is False

    def test_initialization_with_properties(self) -> None:
        """Test initialization with specific properties."""
        properties = DbInstanceProperties(
            DBInstanceIdentifier="db-abc",
            DBInstanceClass="db.t3.micro",
            Engine="mysql",
            DBInstanceStatus="available",
            MultiAZ=True,
            StorageEncrypted=True,
            Tags=[{"Key": "Environment", "Value": "test"}],
        )
        assert properties.DBInstanceIdentifier == "db-abc"
        assert properties.DBInstanceClass == "db.t3.micro"
        assert properties.Engine == "mysql"
        assert properties.DBInstanceStatus == "available"
        assert properties.MultiAZ is True
        assert properties.StorageEncrypted is True
        assert properties.Tags == [{"Key": "Environment", "Value": "test"}]

    def test_dict_exclude_none(self) -> None:
        """Test dict serialization with exclude_none=True."""
        properties = DbInstanceProperties(
            DBInstanceIdentifier="db-123",
            Engine="postgres",
            Tags=[{"Key": "Project", "Value": "demo"}],
        )
        result = properties.dict(exclude_none=True)
        assert result["DBInstanceIdentifier"] == "db-123"
        assert result["Engine"] == "postgres"
        assert result["Tags"] == [{"Key": "Project", "Value": "demo"}]
        # DBInstanceClass is included because it has a default value (empty string), not None
        assert "DBInstanceClass" in result
        assert result["DBInstanceClass"] == ""

    def test_all_properties_assignment(self) -> None:
        """Test assignment of all available properties."""
        properties = DbInstanceProperties(
            AllocatedStorage=100,
            AutoMinorVersionUpgrade=True,
            AvailabilityZone="us-west-2a",
            BackupRetentionPeriod=7,
            CACertificateIdentifier="rds-ca-2015",
            CharacterSetName="utf8",
            CopyTagsToSnapshot=True,
            DBInstanceArn="arn:aws:rds:us-west-2:123456789012:db:db-123",
            DBInstanceClass="db.t3.micro",
            DBInstanceIdentifier="db-123",
            DbInstancePort=3306,
            DBInstanceStatus="available",
            DBName="testdb",
            DBParameterGroups=[{"DBParameterGroupName": "default.mysql5.7"}],
            DBSecurityGroups=[{"DBSecurityGroupName": "default"}],
            DBSubnetGroup={"DBSubnetGroupName": "default"},
            DbiResourceId="db-1234567890",
            DomainMemberships=[],
            IAMDatabaseAuthenticationEnabled=True,
            PerformanceInsightsEnabled=True,
            Endpoint={
                "Address": "db-123.abc123.us-west-2.rds.amazonaws.com",
                "Port": 3306,
            },
            Engine="mysql",
            EngineVersion="5.7.44",
            EnhancedMonitoringResourceArn="arn:aws:logs:us-west-2:123456789012:log-group:RDSOSMetrics",
            InstanceCreateTime=datetime(2023, 1, 1, 0, 0, 0),
            Iops=1000,
            KmsKeyId="arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012",
            LatestRestorableTime=datetime(2023, 1, 2, 0, 0, 0),
            LicenseModel="general-public-license",
            MasterUsername="admin",
            MonitoringInterval=60,
            MonitoringRoleArn="arn:aws:iam::123456789012:role/rds-monitoring-role",
            MultiAZ=True,
            OptionGroupMemberships=[{"OptionGroupName": "default:mysql-5-7"}],
            PendingModifiedValues={},
            PreferredBackupWindow="03:00-04:00",
            PreferredMaintenanceWindow="sun:04:00-sun:05:00",
            PubliclyAccessible=False,
            ReadReplicaDBInstanceIdentifiers=[],
            SecondaryAvailabilityZone="us-west-2b",
            StorageEncrypted=True,
            StorageType="gp2",
            Tags=[{"Key": "Name", "Value": "test-db"}],
            VpcSecurityGroups=[{"VpcSecurityGroupId": "sg-12345678"}],
            DatabaseInsightsMode="standard",
            DeletionProtection=True,
            AssociatedRoles=[],
            CustomerOwnedIpEnabled=False,
            ActivityStreamStatus="stopped",
            BackupTarget="region",
            NetworkType="IPV4",
            StorageThroughput=125,
            CertificateDetails={"CertificateIdentifier": "rds-ca-2015"},
            DedicatedLogVolume=True,
            IsStorageConfigUpgradeAvailable=False,
            EngineLifecycleSupport="supported",
        )

        # Verify key properties
        assert properties.DBInstanceIdentifier == "db-123"
        assert properties.Engine == "mysql"
        assert properties.DBInstanceClass == "db.t3.micro"
        assert properties.MultiAZ is True
        assert properties.StorageEncrypted is True
        assert properties.Tags == [{"Key": "Name", "Value": "test-db"}]

    def test_aliases_work_correctly(self) -> None:
        """Test that field aliases work correctly."""
        properties = DbInstanceProperties(
            IAMDatabaseAuthenticationEnabled=True,
            PerformanceInsightsEnabled=True,
            DbInstancePort=3306,
            VpcSecurityGroups=[{"VpcSecurityGroupId": "sg-123"}],
        )

        # Test that aliases are used in serialization
        result = properties.dict(by_alias=True)
        assert "EnableIAMDatabaseAuthentication" in result
        assert "EnablePerformanceInsights" in result
        assert "Port" in result
        assert "VPCSecurityGroups" in result

        # Test that field names work in direct access
        assert properties.IAMDatabaseAuthenticationEnabled is True
        assert properties.PerformanceInsightsEnabled is True
        assert properties.DbInstancePort == 3306
        assert properties.VpcSecurityGroups == [{"VpcSecurityGroupId": "sg-123"}]


class TestDbInstance:

    def test_initialization_with_identifier(self) -> None:
        """Test initialization with just an identifier."""
        db_instance = DbInstance(
            Properties=DbInstanceProperties(DBInstanceIdentifier="db-1")
        )
        assert db_instance.Type == "AWS::RDS::DBInstance"
        assert db_instance.Properties.DBInstanceIdentifier == "db-1"

    def test_initialization_with_properties(self) -> None:
        """Test initialization with full properties."""
        properties = DbInstanceProperties(
            DBInstanceIdentifier="db-2",
            DBInstanceClass="db.t3.small",
            Engine="postgres",
            MultiAZ=True,
        )
        db_instance = DbInstance(Properties=properties)
        assert db_instance.Properties == properties
        assert db_instance.Properties.DBInstanceIdentifier == "db-2"
        assert db_instance.Properties.DBInstanceClass == "db.t3.small"
        assert db_instance.Properties.Engine == "postgres"
        assert db_instance.Properties.MultiAZ is True

    def test_type_is_fixed(self) -> None:
        """Test that Type is always the same for all instances."""
        db1 = DbInstance(Properties=DbInstanceProperties(DBInstanceIdentifier="db-1"))
        db2 = DbInstance(Properties=DbInstanceProperties(DBInstanceIdentifier="db-2"))
        assert db1.Type == "AWS::RDS::DBInstance"
        assert db2.Type == "AWS::RDS::DBInstance"

    def test_dict_exclude_none(self) -> None:
        """Test dict serialization with exclude_none=True."""
        db_instance = DbInstance(
            Properties=DbInstanceProperties(DBInstanceIdentifier="db-1")
        )
        data = db_instance.dict(exclude_none=True)
        assert data["Type"] == "AWS::RDS::DBInstance"
        assert data["Properties"]["DBInstanceIdentifier"] == "db-1"

    def test_properties_default_factory(self) -> None:
        """Test that Properties uses default_factory correctly."""
        db1 = DbInstance(Properties=DbInstanceProperties(DBInstanceIdentifier="db-1"))
        db2 = DbInstance(Properties=DbInstanceProperties(DBInstanceIdentifier="db-2"))
        assert db1.Properties is not db2.Properties
        assert db1.Properties.DBInstanceIdentifier == "db-1"
        assert db2.Properties.DBInstanceIdentifier == "db-2"

    def test_complex_properties_serialization(self) -> None:
        """Test serialization of complex nested properties."""
        properties = DbInstanceProperties(
            DBInstanceIdentifier="db-complex",
            Endpoint={
                "Address": "db-complex.abc123.us-west-2.rds.amazonaws.com",
                "Port": 3306,
                "HostedZoneId": "Z2R2ITUGPM61AM",
            },
            DBParameterGroups=[
                {
                    "DBParameterGroupName": "default.mysql5.7",
                    "ParameterApplyStatus": "in-sync",
                }
            ],
            Tags=[
                {"Key": "Environment", "Value": "production"},
                {"Key": "Project", "Value": "web-app"},
            ],
        )
        db_instance = DbInstance(Properties=properties)

        data = db_instance.dict(exclude_none=True)
        assert (
            data["Properties"]["Endpoint"]["Address"]
            == "db-complex.abc123.us-west-2.rds.amazonaws.com"
        )
        assert data["Properties"]["Endpoint"]["Port"] == 3306
        assert len(data["Properties"]["DBParameterGroups"]) == 1
        assert len(data["Properties"]["Tags"]) == 2
