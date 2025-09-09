import pytest
from pydantic import ValidationError

from aws.core.exporters.s3.bucket.models import (
    Bucket,
    BucketProperties,
    SingleBucketRequest,
    PaginatedBucketRequest,
)
from datetime import datetime


class TestExporterOptions:
    """Test the base ExporterOptions class."""

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with only required fields."""
        options = SingleBucketRequest(
            region="us-west-2", account_id="123456789012", bucket_name="test-bucket"
        )

        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.include == []  # Default empty list

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["GetBucketTaggingAction", "GetBucketEncryptionAction"]
        options = SingleBucketRequest(
            region="eu-central-1",
            account_id="123456789012",
            bucket_name="test-bucket",
            include=include_list,
        )

        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        """Test that missing region raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleBucketRequest(
                bucket_name="test-bucket", account_id="123456789012"  # type: ignore
            )

        assert "region" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        """Test with explicitly empty include list."""
        options = SingleBucketRequest(
            region="us-east-1",
            account_id="123456789012",
            bucket_name="test-bucket",
            include=[],
        )

        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        """Test include list with various values."""
        options = SingleBucketRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            bucket_name="test-bucket",
            include=["Action1", "Action2", "Action3"],
        )

        assert len(options.include) == 3
        assert "Action1" in options.include
        assert "Action2" in options.include
        assert "Action3" in options.include


class TestSingleS3BucketExporterOptions:
    """Test the SingleS3BucketExporterOptions class."""

    def test_inheritance(self) -> None:
        """Test that SingleS3BucketExporterOptions inherits from ExporterOptions."""
        options = SingleBucketRequest(
            region="us-west-2", account_id="123456789012", bucket_name="test-bucket"
        )

        assert isinstance(options, SingleBucketRequest)

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields."""
        options = SingleBucketRequest(
            region="us-west-2",
            account_id="123456789012",
            bucket_name="my-test-bucket",
        )

        assert options.region == "us-west-2"
        assert options.bucket_name == "my-test-bucket"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["GetBucketTaggingAction", "GetBucketEncryptionAction"]
        options = SingleBucketRequest(
            region="eu-west-1",
            account_id="123456789012",
            bucket_name="production-bucket",
            include=include_list,
        )

        assert options.region == "eu-west-1"
        assert options.bucket_name == "production-bucket"
        assert options.include == include_list

    def test_missing_bucket_name(self) -> None:
        """Test that missing bucket_name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleBucketRequest(region="us-west-2", account_id="123456789012")  # type: ignore

        assert "bucket_name" in str(exc_info.value)

    def test_missing_region(self) -> None:
        """Test that missing region raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleBucketRequest(
                bucket_name="test-bucket", account_id="123456789012"
            )  # type: ignore

        assert "region" in str(exc_info.value)

    def test_bucket_name_validation(self) -> None:
        """Test bucket name with various valid formats."""
        valid_bucket_names = [
            "simple-bucket",
            "bucket.with.dots",
            "bucket-123",
            "my-very-long-bucket-name-with-many-hyphens",
            "a" * 63,  # Maximum length
        ]

        for bucket_name in valid_bucket_names:
            options = SingleBucketRequest(
                region="us-west-2",
                account_id="123456789012",
                bucket_name=bucket_name,
            )
            assert options.bucket_name == bucket_name


class TestPaginatedS3BucketExporterOptions:
    """Test the PaginatedS3BucketExporterOptions class."""

    def test_inheritance(self) -> None:
        """Test that PaginatedS3BucketExporterOptions inherits from ExporterOptions."""
        options = PaginatedBucketRequest(region="us-west-2", account_id="123456789012")

        assert isinstance(options, PaginatedBucketRequest)

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with only required fields."""
        options = PaginatedBucketRequest(region="us-east-1", account_id="123456789012")

        assert options.region == "us-east-1"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        """Test initialization with include list."""
        include_list = ["GetBucketPublicAccessBlockAction", "GetBucketTaggingAction"]
        options = PaginatedBucketRequest(
            region="ap-southeast-2", account_id="123456789012", include=include_list
        )

        assert options.region == "ap-southeast-2"
        assert options.include == include_list

    def test_no_additional_fields(self) -> None:
        """Test that PaginatedS3BucketExporterOptions doesn't add additional fields."""
        options = PaginatedBucketRequest(region="eu-north-1", account_id="123456789012")

        # Should only have the fields from ExporterOptions
        assert hasattr(options, "region")
        assert hasattr(options, "include")
        assert hasattr(options, "account_id")
        assert not hasattr(options, "bucket_name")


class TestS3BucketProperties:
    """Test the S3BucketProperties model."""

    def test_initialization_empty(self) -> None:
        """Test initialization with no properties."""
        properties = BucketProperties()

        # Core fields have defaults
        assert properties.BucketName == ""
        assert properties.Arn == ""
        assert properties.CreationDate is None
        # Optional fields
        assert properties.LocationConstraint is None
        assert properties.Tags == []
        assert properties.BucketEncryption is None
        assert properties.PublicAccessBlockConfiguration is None
        assert properties.OwnershipControls is None

    def test_initialization_with_properties(self) -> None:
        """Test initialization with some properties."""
        properties = BucketProperties(
            BucketName="test-bucket",
            Tags=[{"Key": "Environment", "Value": "test"}],
            PublicAccessBlockConfiguration={"BlockPublicAcls": True},
        )

        assert properties.BucketName == "test-bucket"
        assert properties.Tags == [{"Key": "Environment", "Value": "test"}]
        assert properties.PublicAccessBlockConfiguration == {"BlockPublicAcls": True}

    def test_dict_exclude_none(self) -> None:
        """Test dict() with exclude_none=True."""
        properties = BucketProperties(
            BucketName="test-bucket", Tags=[{"Key": "Project", "Value": "demo"}]
        )

        result = properties.dict(exclude_none=True)

        # Should only include non-None fields
        assert "BucketName" in result
        assert "Tags" in result
        assert result["BucketName"] == "test-bucket"
        assert result["Tags"] == [{"Key": "Project", "Value": "demo"}]

        # None optional fields should be excluded
        assert "BucketEncryption" not in result
        assert "OwnershipControls" not in result

    def test_all_properties_assignment(self) -> None:
        """Test assignment of all available properties."""
        properties = BucketProperties(
            BucketName="test-bucket",
            Arn="arn:aws:s3:::test-bucket",
            CreationDate=datetime(2025, 1, 1, 0, 0, 0),
            LocationConstraint="us-west-2",
            Tags=[{"Key": "Owner", "Value": "team"}],
            BucketEncryption={"Rules": []},
            PublicAccessBlockConfiguration={"BlockPublicAcls": True},
            OwnershipControls={"Rules": []},
        )

        # Verify key properties are set
        assert properties.BucketName == "test-bucket"
        assert properties.Arn == "arn:aws:s3:::test-bucket"
        assert properties.CreationDate == datetime(2025, 1, 1, 0, 0, 0)
        assert properties.LocationConstraint == "us-west-2"
        assert properties.Tags == [{"Key": "Owner", "Value": "team"}]
        assert properties.BucketEncryption == {"Rules": []}
        assert properties.PublicAccessBlockConfiguration == {"BlockPublicAcls": True}
        assert properties.OwnershipControls == {"Rules": []}


class TestS3Bucket:
    """Test the S3Bucket model."""

    def test_initialization_with_identifier(self) -> None:
        """Test initialization with required identifier."""
        bucket = Bucket(Properties=BucketProperties(BucketName="test-bucket"))

        assert bucket.Type == "AWS::S3::Bucket"
        assert bucket.Properties.BucketName == "test-bucket"
        assert isinstance(bucket.Properties, BucketProperties)

    def test_initialization_with_properties(self) -> None:
        """Test initialization with custom properties."""
        properties = BucketProperties(
            BucketName="custom-bucket",
            Tags=[{"Key": "Team", "Value": "engineering"}],
        )
        bucket = Bucket(Properties=properties)

        assert bucket.Properties == properties
        assert bucket.Properties.BucketName == "custom-bucket"
        assert bucket.Properties.Tags == [{"Key": "Team", "Value": "engineering"}]

    def test_type_is_fixed(self) -> None:
        """Test that Type is always AWS::S3::Bucket."""
        bucket1 = Bucket(Properties=BucketProperties(BucketName="bucket1"))
        bucket2 = Bucket(Properties=BucketProperties(BucketName="bucket2"))

        assert bucket1.Type == "AWS::S3::Bucket"
        assert bucket2.Type == "AWS::S3::Bucket"

    def test_dict_exclude_none(self) -> None:
        """Test dict() with exclude_none=True."""
        properties = BucketProperties(BucketName="test-bucket")
        bucket = Bucket(Properties=properties)

        result = bucket.dict(exclude_none=True)

        assert "Type" in result
        assert "Properties" in result

        assert result["Type"] == "AWS::S3::Bucket"
        assert result["Properties"]["BucketName"] == "test-bucket"

    def test_properties_default_factory(self) -> None:
        """Test that Properties uses default factory."""
        bucket1 = Bucket(Properties=BucketProperties(BucketName="bucket1"))
        bucket2 = Bucket(Properties=BucketProperties(BucketName="bucket2"))

        # Should be different instances
        assert bucket1.Properties is not bucket2.Properties

        # But both should be BucketProperties instances
        assert isinstance(bucket1.Properties, BucketProperties)
        assert isinstance(bucket2.Properties, BucketProperties)

    def test_bucket_serialization_roundtrip(self) -> None:
        """Test that bucket can be serialized and deserialized."""
        original_bucket = Bucket(
            Properties=BucketProperties(
                BucketName="roundtrip-bucket",
                Tags=[{"Key": "Test", "Value": "roundtrip"}],
                BucketEncryption={
                    "Rules": [
                        {
                            "ApplyServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "AES256"
                            }
                        }
                    ]
                },
            ),
        )

        # Serialize to dict
        bucket_dict = original_bucket.dict()

        # Deserialize back to object
        recreated_bucket = Bucket(**bucket_dict)

        # Verify they're equivalent
        assert recreated_bucket.Type == original_bucket.Type
        assert (
            recreated_bucket.Properties.BucketName
            == original_bucket.Properties.BucketName
        )
        assert recreated_bucket.Properties.Tags == original_bucket.Properties.Tags
        assert (
            recreated_bucket.Properties.BucketEncryption
            == original_bucket.Properties.BucketEncryption
        )
