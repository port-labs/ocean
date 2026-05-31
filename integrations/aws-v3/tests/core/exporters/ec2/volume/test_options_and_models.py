from datetime import datetime
import pytest
from pydantic import ValidationError

from aws.core.exporters.ec2.volume.models import (
    EbsVolume,
    EbsVolumeProperties,
    SingleEbsVolumeRequest,
    PaginatedEbsVolumeRequest,
)


class TestSingleEbsVolumeRequest:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleEbsVolumeRequest(
            region="us-east-1", account_id="123456789012", volume_id="vol-111"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.volume_id == "vol-111"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        include_list = ["DescribeVolumeAttributeAction"]
        options = SingleEbsVolumeRequest(
            region="eu-west-1",
            account_id="123456789012",
            volume_id="vol-222",
            include=include_list,
        )
        assert options.volume_id == "vol-222"
        assert options.include == include_list

    def test_missing_required_volume_id(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleEbsVolumeRequest(region="us-east-1", account_id="123456789012")  # type: ignore
        assert "volume_id" in str(exc_info.value)


class TestPaginatedEbsVolumeRequest:

    def test_inheritance(self) -> None:
        options = PaginatedEbsVolumeRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert isinstance(options, PaginatedEbsVolumeRequest)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedEbsVolumeRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert options.region == "us-west-2"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        options = PaginatedEbsVolumeRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            include=["DescribeVolumeAttributeAction"],
        )
        assert options.include == ["DescribeVolumeAttributeAction"]


class TestEbsVolumeProperties:

    def test_initialization_empty(self) -> None:
        properties = EbsVolumeProperties()
        assert properties.VolumeId == ""
        assert properties.VolumeType is None
        assert properties.Size is None
        assert properties.Iops is None
        assert properties.Throughput is None
        assert properties.AvailabilityZone is None
        assert properties.State is None
        assert properties.CreateTime is None
        assert properties.Tags is None
        assert properties.Encrypted is None
        assert properties.AutoEnableIO is None

    def test_initialization_with_properties(self) -> None:
        properties = EbsVolumeProperties(
            VolumeId="vol-111",
            VolumeType="gp3",
            Size=100,
            Iops=3000,
            Throughput=125,
            AvailabilityZone="us-east-1a",
            State="available",
            CreateTime=datetime(2025, 1, 1, 0, 0, 0),
            Encrypted=True,
            AutoEnableIO=False,
            Tags=[{"Key": "Name", "Value": "my-volume"}],
        )
        assert properties.VolumeId == "vol-111"
        assert properties.VolumeType == "gp3"
        assert properties.Size == 100
        assert properties.Iops == 3000
        assert properties.Throughput == 125
        assert properties.AvailabilityZone == "us-east-1a"
        assert properties.State == "available"
        assert properties.Encrypted is True
        assert properties.AutoEnableIO is False
        assert properties.Tags == [{"Key": "Name", "Value": "my-volume"}]

    def test_dict_exclude_none(self) -> None:
        properties = EbsVolumeProperties(VolumeId="vol-111", VolumeType="gp3")
        result = properties.dict(exclude_none=True)
        assert result["VolumeId"] == "vol-111"
        assert result["VolumeType"] == "gp3"
        assert "Size" not in result
        assert "AutoEnableIO" not in result


class TestEbsVolume:

    def test_type_is_fixed(self) -> None:
        vol1 = EbsVolume(Properties=EbsVolumeProperties(VolumeId="vol-111"))
        vol2 = EbsVolume(Properties=EbsVolumeProperties(VolumeId="vol-222"))
        assert vol1.Type == "AWS::EC2::Volume"
        assert vol2.Type == "AWS::EC2::Volume"

    def test_initialization_with_properties(self) -> None:
        properties = EbsVolumeProperties(VolumeId="vol-111", VolumeType="io2", Size=500)
        volume = EbsVolume(Properties=properties)
        assert volume.Properties == properties
        assert volume.Properties.VolumeId == "vol-111"
        assert volume.Properties.VolumeType == "io2"

    def test_dict_exclude_none(self) -> None:
        volume = EbsVolume(Properties=EbsVolumeProperties(VolumeId="vol-111"))
        data = volume.dict(exclude_none=True)
        assert data["Type"] == "AWS::EC2::Volume"
        assert data["Properties"]["VolumeId"] == "vol-111"

    def test_properties_default_factory(self) -> None:
        vol1 = EbsVolume(Properties=EbsVolumeProperties(VolumeId="vol-111"))
        vol2 = EbsVolume(Properties=EbsVolumeProperties(VolumeId="vol-222"))
        assert vol1.Properties is not vol2.Properties
        assert vol1.Properties.VolumeId == "vol-111"
        assert vol2.Properties.VolumeId == "vol-222"
