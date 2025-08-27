import pytest
from datetime import datetime
from pydantic import ValidationError

from aws.core.exporters.ec2.instances.models import (
    EC2Instance,
    EC2InstanceProperties,
    SingleEC2InstanceRequest,
    PaginatedEC2InstanceRequest,
)


class TestEC2InstanceProperties:
    """Test the EC2InstanceProperties model."""

    def test_initialization_empty(self) -> None:
        """Test initialization with no properties."""
        properties = EC2InstanceProperties()

        # All fields should be None initially except InstanceId which defaults to empty string
        assert properties.InstanceId == ""
        assert properties.InstanceType is None
        assert properties.State is None
        assert properties.PublicIpAddress is None
        assert properties.PrivateIpAddress is None
        assert properties.InstanceArn is None
        assert properties.Tags is None

    def test_initialization_with_properties(self) -> None:
        """Test initialization with some properties."""
        properties = EC2InstanceProperties(
            InstanceId="i-1234567890abcdef0",
            InstanceType="t3.micro",
            State={"Name": "running", "Code": 16},
            PublicIpAddress="203.0.113.12",
            PrivateIpAddress="10.0.1.55",
            Tags=[{"Key": "Environment", "Value": "test"}],
        )

        assert properties.InstanceId == "i-1234567890abcdef0"
        assert properties.InstanceType == "t3.micro"
        assert properties.State == {"Name": "running", "Code": 16}
        assert properties.PublicIpAddress == "203.0.113.12"
        assert properties.PrivateIpAddress == "10.0.1.55"
        assert properties.Tags == [{"Key": "Environment", "Value": "test"}]

        # Non-specified fields should be None
        assert properties.ImageId is None
        assert properties.LaunchTime is None

    def test_dict_exclude_none(self) -> None:
        """Test dict() with exclude_none=True."""
        properties = EC2InstanceProperties(
            InstanceId="i-1234567890abcdef0",
            InstanceType="t3.micro",
            Tags=[{"Key": "Project", "Value": "demo"}],
        )

        result = properties.dict(exclude_none=True)

        # Should only include non-None fields
        assert "InstanceId" in result
        assert "InstanceType" in result
        assert "Tags" in result
        assert result["InstanceId"] == "i-1234567890abcdef0"
        assert result["InstanceType"] == "t3.micro"
        assert result["Tags"] == [{"Key": "Project", "Value": "demo"}]

        # None fields should be excluded
        assert "State" not in result
        assert "PublicIpAddress" not in result
        assert "PrivateIpAddress" not in result

    def test_all_properties_assignment(self) -> None:
        """Test assignment of all available properties."""
        launch_time = datetime.now()
        properties = EC2InstanceProperties(
            InstanceId="i-1234567890abcdef0",
            InstanceType="t3.medium",
            State={"Name": "running", "Code": 16},
            PublicIpAddress="203.0.113.12",
            PrivateIpAddress="10.0.1.55",
            InstanceArn="arn:aws:ec2:us-west-2:123456789012:instance/i-1234567890abcdef0",
            Tags=[{"Key": "Owner", "Value": "team"}],
            ImageId="ami-0abcdef1234567890",
            LaunchTime=launch_time,
            Placement={"AvailabilityZone": "us-west-2a"},
            VpcId="vpc-12345678",
            SubnetId="subnet-12345678",
            SecurityGroups=[{"GroupId": "sg-12345678", "GroupName": "default"}],
            IamInstanceProfile={
                "Arn": "arn:aws:iam::123456789012:instance-profile/MyRole"
            },
            KeyName="my-key-pair",
            Platform="Linux/UNIX",
            PlatformDetails="Linux/UNIX",
            Architecture="x86_64",
            Hypervisor="xen",
            VirtualizationType="hvm",
            Monitoring={"State": "enabled"},
            EbsOptimized=True,
        )

        # Verify all properties are set
        assert properties.InstanceId == "i-1234567890abcdef0"
        assert properties.InstanceType == "t3.medium"
        assert properties.State == {"Name": "running", "Code": 16}
        assert properties.PublicIpAddress == "203.0.113.12"
        assert properties.PrivateIpAddress == "10.0.1.55"
        assert properties.Tags == [{"Key": "Owner", "Value": "team"}]
        assert properties.ImageId == "ami-0abcdef1234567890"
        assert properties.LaunchTime == launch_time
        assert properties.Placement == {"AvailabilityZone": "us-west-2a"}
        assert properties.VpcId == "vpc-12345678"
        assert properties.EbsOptimized is True


class TestEC2Instance:
    """Test the EC2Instance model."""

    def test_initialization_with_properties(self) -> None:
        """Test initialization with custom properties."""
        properties = EC2InstanceProperties(
            InstanceId="i-1234567890abcdef0",
            InstanceType="t3.micro",
            Tags=[{"Key": "Team", "Value": "engineering"}],
        )
        instance = EC2Instance(Properties=properties)

        assert instance.Type == "AWS::EC2::Instance"
        assert instance.Properties == properties
        assert instance.Properties.InstanceId == "i-1234567890abcdef0"
        assert instance.Properties.InstanceType == "t3.micro"
        assert instance.Properties.Tags == [{"Key": "Team", "Value": "engineering"}]

    def test_type_is_fixed(self) -> None:
        """Test that Type is always AWS::EC2::Instance."""
        instance1 = EC2Instance(
            Properties=EC2InstanceProperties(InstanceId="i-1234567890abcdef0")
        )
        instance2 = EC2Instance(
            Properties=EC2InstanceProperties(InstanceId="i-0987654321fedcba0")
        )

        assert instance1.Type == "AWS::EC2::Instance"
        assert instance2.Type == "AWS::EC2::Instance"

    def test_dict_exclude_none(self) -> None:
        """Test dict() with exclude_none=True."""
        properties = EC2InstanceProperties(
            InstanceId="i-1234567890abcdef0",
            InstanceType="t3.micro",
        )
        instance = EC2Instance(Properties=properties)

        result = instance.dict(exclude_none=True)

        assert "Type" in result
        assert "Properties" in result
        assert result["Type"] == "AWS::EC2::Instance"
        assert result["Properties"]["InstanceId"] == "i-1234567890abcdef0"
        assert result["Properties"]["InstanceType"] == "t3.micro"

    def test_properties_default_factory(self) -> None:
        """Test that Properties uses default factory."""
        instance1 = EC2Instance(
            Properties=EC2InstanceProperties(InstanceId="i-1234567890abcdef0")
        )
        instance2 = EC2Instance(
            Properties=EC2InstanceProperties(InstanceId="i-0987654321fedcba0")
        )

        # Should be different instances
        assert instance1.Properties is not instance2.Properties

        # But both should be EC2InstanceProperties instances
        assert isinstance(instance1.Properties, EC2InstanceProperties)
        assert isinstance(instance2.Properties, EC2InstanceProperties)

    def test_instance_serialization_roundtrip(self) -> None:
        """Test that instance can be serialized and deserialized."""
        original_instance = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-1234567890abcdef0",
                InstanceType="t3.medium",
                State={"Name": "running", "Code": 16},
                Tags=[{"Key": "Test", "Value": "roundtrip"}],
                SecurityGroups=[{"GroupId": "sg-12345678", "GroupName": "default"}],
            ),
        )

        # Serialize to dict
        instance_dict = original_instance.dict()

        # Deserialize back to object
        recreated_instance = EC2Instance(**instance_dict)

        # Verify they're equivalent
        assert recreated_instance.Type == original_instance.Type
        assert (
            recreated_instance.Properties.InstanceId
            == original_instance.Properties.InstanceId
        )
        assert (
            recreated_instance.Properties.InstanceType
            == original_instance.Properties.InstanceType
        )
        assert recreated_instance.Properties.State == original_instance.Properties.State
        assert recreated_instance.Properties.Tags == original_instance.Properties.Tags
        assert (
            recreated_instance.Properties.SecurityGroups
            == original_instance.Properties.SecurityGroups
        )


class TestSingleEC2InstanceRequest:
    """Test the SingleEC2InstanceRequest class."""

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields."""
        options = SingleEC2InstanceRequest(
            region="us-west-2", instance_id="i-1234567890abcdef0"
        )

        assert options.region == "us-west-2"
        assert options.instance_id == "i-1234567890abcdef0"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["GetInstanceTagsAction", "GetInstanceStatusAction"]
        options = SingleEC2InstanceRequest(
            region="eu-central-1",
            instance_id="i-1234567890abcdef0",
            include=include_list,
        )

        assert options.region == "eu-central-1"
        assert options.instance_id == "i-1234567890abcdef0"
        assert options.include == include_list

    def test_missing_instance_id(self) -> None:
        """Test that missing instance_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleEC2InstanceRequest(region="us-west-2")  # type: ignore

        assert "instance_id" in str(exc_info.value)

    def test_optional_region(self) -> None:
        """Test that region is optional and defaults to None."""
        options = SingleEC2InstanceRequest(instance_id="i-1234567890abcdef0")

        assert options.instance_id == "i-1234567890abcdef0"
        assert options.region is None

    def test_instance_id_validation(self) -> None:
        """Test instance ID with various valid formats."""
        valid_instance_ids = [
            "i-1234567890abcdef0",
            "i-0123456789abcdef0",
            "i-abcdef1234567890",
        ]

        for instance_id in valid_instance_ids:
            options = SingleEC2InstanceRequest(
                region="us-west-2", instance_id=instance_id
            )
            assert options.instance_id == instance_id


class TestPaginatedEC2InstanceRequest:
    """Test the PaginatedEC2InstanceRequest class."""

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with only required fields."""
        options = PaginatedEC2InstanceRequest(region="us-east-1")

        assert options.region == "us-east-1"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        """Test initialization with include list."""
        include_list = ["GetInstanceStatusAction", "GetInstanceTagsAction"]
        options = PaginatedEC2InstanceRequest(
            region="ap-southeast-2", include=include_list
        )

        assert options.region == "ap-southeast-2"
        assert options.include == include_list

    def test_optional_region_paginated(self) -> None:
        """Test that region is optional for paginated requests too."""
        options = PaginatedEC2InstanceRequest()

        assert options.region is None
        assert options.include == []

    def test_no_additional_fields(self) -> None:
        """Test that PaginatedEC2InstanceRequest doesn't add additional fields."""
        options = PaginatedEC2InstanceRequest(region="eu-north-1")

        # Should only have the fields from ResourceRequestModel
        assert hasattr(options, "region")
        assert hasattr(options, "include")
        assert not hasattr(options, "instance_id")
