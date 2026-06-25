import pytest
from pydantic.v1 import ValidationError

from aws.core.exporters.ec2.volume_attachment.models import (
    EC2VolumeAttachment,
    EC2VolumeAttachmentProperties,
    SingleEC2VolumeAttachmentRequest,
    PaginatedEC2VolumeAttachmentRequest,
)


class TestSingleEC2VolumeAttachmentRequest:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleEC2VolumeAttachmentRequest(
            region="us-east-1",
            account_id="123456789012",
            volume_id="vol-09a13562b4dacdee2",
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.volume_id == "vol-09a13562b4dacdee2"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        options = SingleEC2VolumeAttachmentRequest(
            region="eu-west-1",
            account_id="123456789012",
            volume_id="vol-abc123",
            include=[],
        )
        assert options.volume_id == "vol-abc123"
        assert options.include == []

    def test_missing_required_volume_id(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleEC2VolumeAttachmentRequest(  # type: ignore
                region="us-east-1", account_id="123456789012"
            )
        assert "volume_id" in str(exc_info.value)


class TestPaginatedEC2VolumeAttachmentRequest:

    def test_inheritance(self) -> None:
        options = PaginatedEC2VolumeAttachmentRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert isinstance(options, PaginatedEC2VolumeAttachmentRequest)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedEC2VolumeAttachmentRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert options.region == "us-west-2"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        options = PaginatedEC2VolumeAttachmentRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            include=[],
        )
        assert options.include == []


class TestEC2VolumeAttachmentProperties:

    def test_initialization_empty(self) -> None:
        properties = EC2VolumeAttachmentProperties()
        assert properties.VolumeId == ""
        assert properties.InstanceId == ""
        assert properties.Device is None
        assert properties.State is None
        assert properties.AttachTime is None
        assert properties.DeleteOnTermination is None

    def test_initialization_with_properties(self) -> None:
        properties = EC2VolumeAttachmentProperties(
            VolumeId="vol-09a13562b4dacdee2",
            InstanceId="i-0abcdef1234567890",
            Device="/dev/sda1",
            State="attached",
            AttachTime="2024-04-17T20:10:00+00:00",
            DeleteOnTermination=True,
        )
        assert properties.VolumeId == "vol-09a13562b4dacdee2"
        assert properties.InstanceId == "i-0abcdef1234567890"
        assert properties.Device == "/dev/sda1"
        assert properties.State == "attached"
        assert properties.AttachTime == "2024-04-17T20:10:00+00:00"
        assert properties.DeleteOnTermination is True

    def test_dict_exclude_none(self) -> None:
        properties = EC2VolumeAttachmentProperties(
            VolumeId="vol-111",
            InstanceId="i-abc123",
            State="attached",
        )
        result = properties.dict(exclude_none=True)
        assert result["VolumeId"] == "vol-111"
        assert result["InstanceId"] == "i-abc123"
        assert result["State"] == "attached"
        assert "Device" not in result
        assert "AttachTime" not in result


class TestEC2VolumeAttachment:

    def test_type_is_fixed(self) -> None:
        attachment1 = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-111", InstanceId="i-111"
            )
        )
        attachment2 = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-222", InstanceId="i-222"
            )
        )
        assert attachment1.Type == "AWS::EC2::VolumeAttachment"
        assert attachment2.Type == "AWS::EC2::VolumeAttachment"

    def test_initialization_with_properties(self) -> None:
        properties = EC2VolumeAttachmentProperties(
            VolumeId="vol-111",
            InstanceId="i-abc123",
            Device="/dev/sda1",
            State="attached",
        )
        attachment = EC2VolumeAttachment(Properties=properties)
        assert attachment.Properties == properties
        assert attachment.Properties.VolumeId == "vol-111"
        assert attachment.Properties.InstanceId == "i-abc123"

    def test_dict_exclude_none(self) -> None:
        attachment = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-111", InstanceId="i-abc123"
            )
        )
        data = attachment.dict(exclude_none=True)
        assert data["Type"] == "AWS::EC2::VolumeAttachment"
        assert data["Properties"]["VolumeId"] == "vol-111"
        assert data["Properties"]["InstanceId"] == "i-abc123"

    def test_properties_default_factory(self) -> None:
        attachment1 = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-111", InstanceId="i-111"
            )
        )
        attachment2 = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-222", InstanceId="i-222"
            )
        )
        assert attachment1.Properties is not attachment2.Properties
        assert attachment1.Properties.VolumeId == "vol-111"
        assert attachment2.Properties.VolumeId == "vol-222"
