import pytest
from pydantic import ValidationError
from datetime import datetime

from aws.core.exporters.ec2.instance.models import (
    EC2Instance,
    EC2InstanceProperties,
    SingleEC2InstanceRequest,
    PaginatedEC2InstanceRequest,
)


class TestExporterOptions:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleEC2InstanceRequest(
            region="us-west-2", account_id="123456789012", instance_id="i-1"
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.instance_id == "i-1"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        include_list = ["GetInstanceStatusAction"]
        options = SingleEC2InstanceRequest(
            region="eu-central-1",
            account_id="123456789012",
            instance_id="i-2",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.instance_id == "i-2"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleEC2InstanceRequest(account_id="123456789012", instance_id="i-1")  # type: ignore
        assert "region" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        options = SingleEC2InstanceRequest(
            region="us-east-1", account_id="123456789012", instance_id="i-3", include=[]
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        options = SingleEC2InstanceRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            instance_id="i-3",
            include=["Action1", "Action2"],
        )
        assert len(options.include) == 2
        assert "Action1" in options.include
        assert "Action2" in options.include


class TestPaginatedEC2InstanceRequest:

    def test_inheritance(self) -> None:
        options = PaginatedEC2InstanceRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedEC2InstanceRequest)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedEC2InstanceRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["GetInstanceStatusAction"]
        options = PaginatedEC2InstanceRequest(
            region="ap-southeast-2", account_id="123456789012", include=include_list
        )
        assert options.region == "ap-southeast-2"
        assert options.include == include_list


class TestEC2InstanceProperties:

    def test_initialization_empty(self) -> None:
        properties = EC2InstanceProperties()
        assert properties.InstanceId == ""
        assert properties.Architecture is None
        assert properties.InstanceType is None
        assert properties.Tags is None

    def test_initialization_with_properties(self) -> None:
        properties = EC2InstanceProperties(
            InstanceId="i-abc",
            InstanceType="t3.micro",
            Tags=[{"Key": "Environment", "Value": "test"}],
        )
        assert properties.InstanceId == "i-abc"
        assert properties.InstanceType == "t3.micro"
        assert properties.Tags == [{"Key": "Environment", "Value": "test"}]

    def test_dict_exclude_none(self) -> None:
        properties = EC2InstanceProperties(
            InstanceId="i-123",
            Tags=[{"Key": "Project", "Value": "demo"}],
        )
        result = properties.dict(exclude_none=True)
        assert result["InstanceId"] == "i-123"
        assert result["Tags"] == [{"Key": "Project", "Value": "demo"}]
        assert "InstanceType" not in result

    def test_all_properties_assignment(self) -> None:
        properties = EC2InstanceProperties(
            AmiLaunchIndex=1,
            Architecture="x86_64",
            AvailabilityZone="us-west-2a",
            BlockDeviceMappings=[{"DeviceName": "/dev/xvda"}],
            BootMode="uefi",
            CapacityReservationSpecification={"CapacityReservationPreference": "open"},
            ClientToken="token",
            CpuOptions={"CoreCount": 2, "ThreadsPerCore": 2},
            CurrentInstanceBootMode="uefi-preferred",
            EbsOptimized=True,
            EnclaveOptions={"Enabled": False},
            EnaSupport=True,
            Events=[{"Code": "pending-reboot"}],
            HibernationOptions={"Configured": False},
            Hypervisor="xen",
            IamInstanceProfile={"Arn": "arn:aws:iam::123:instance-profile/x"},
            ImageId="ami-123",
            InstanceArn="arn:aws:ec2:...:instance/i-123",
            InstanceId="i-123",
            InstanceStatus={"Status": "ok"},
            InstanceState={"Name": "running"},
            InstanceType="t3.micro",
            KeyName="my-key",
            LaunchTime=datetime(2025, 1, 1, 0, 0, 0),
            MaintenanceOptions={"AutoRecovery": "default"},
            MetadataOptions={"HttpTokens": "optional"},
            Monitoring={"State": "disabled"},
            NetworkInterfaces=[{"NetworkInterfaceId": "eni-1"}],
            NetworkPerformanceOptions={"BaselineBandwidthInGbps": 5},
            Operator={"Name": "test"},
            Placement={"Tenancy": "default"},
            Platform="Linux/UNIX",
            PlatformDetails="Linux/UNIX",
            PrivateDnsName="ip-1.ec2.internal",
            PrivateDnsNameOptions={"HostnameType": "ip-name"},
            PrivateIpAddress="10.0.0.1",
            ProductCodes=[{"ProductCodeId": "abc"}],
            PublicDnsName="ec2-1.compute.amazonaws.com",
            PublicIpAddress="54.0.0.1",
            Reason=None,
            RootDeviceName="/dev/xvda",
            RootDeviceType="ebs",
            SecurityGroups=[{"GroupId": "sg-1"}],
            SourceDestCheck=True,
            State={"Name": "running"},
            StateReason=None,
            StateTransitionReason=None,
            SubnetId="subnet-1",
            SystemStatus={"Status": "ok"},
            Tags=[{"Key": "Name", "Value": "server"}],
            UsageOperation="RunInstances:0002",
            UsageOperationUpdateTime=datetime(2025, 1, 1, 0, 0, 0),
            VirtualizationType="hvm",
            VpcId="vpc-1",
        )
        assert properties.InstanceId == "i-123"
        assert properties.Architecture == "x86_64"
        assert properties.InstanceType == "t3.micro"
        assert properties.Tags == [{"Key": "Name", "Value": "server"}]


class TestEC2Instance:

    def test_initialization_with_identifier(self) -> None:
        instance = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-1"))
        assert instance.Type == "AWS::EC2::Instance"
        assert instance.Properties.InstanceId == "i-1"

    def test_initialization_with_properties(self) -> None:
        properties = EC2InstanceProperties(
            InstanceId="i-2",
            InstanceType="t3.small",
        )
        instance = EC2Instance(Properties=properties)
        assert instance.Properties == properties
        assert instance.Properties.InstanceId == "i-2"
        assert instance.Properties.InstanceType == "t3.small"

    def test_type_is_fixed(self) -> None:
        inst1 = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-1"))
        inst2 = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-2"))
        assert inst1.Type == "AWS::EC2::Instance"
        assert inst2.Type == "AWS::EC2::Instance"

    def test_dict_exclude_none(self) -> None:
        instance = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-1"))
        data = instance.dict(exclude_none=True)
        assert data["Type"] == "AWS::EC2::Instance"
        assert data["Properties"]["InstanceId"] == "i-1"

    def test_properties_default_factory(self) -> None:
        inst1 = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-1"))
        inst2 = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-2"))
        assert inst1.Properties is not inst2.Properties
        assert inst1.Properties.InstanceId == "i-1"
        assert inst2.Properties.InstanceId == "i-2"
