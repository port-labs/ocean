import pytest
from pydantic import ValidationError

from aws.core.exporters.s3.bucket.models import (
    Bucket,
    BucketProperties,
    SingleBucketRequest,
    PaginatedBucketRequest,
)


class TestExporterOptions:
    """Test the base ExporterOptions class."""

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with only required fields."""
        options = SingleBucketRequest(region="us-west-2", bucket_name="test-bucket")

        assert options.region == "us-west-2"
        assert options.include == []  # Default empty list

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["GetBucketTaggingAction", "GetBucketEncryptionAction"]
        options = SingleBucketRequest(
            region="eu-central-1", bucket_name="test-bucket", include=include_list
        )

        assert options.region == "eu-central-1"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        """Test that missing region raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleBucketRequest(bucket_name="test-bucket")  # type: ignore

        assert "region" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        """Test with explicitly empty include list."""
        options = SingleBucketRequest(
            region="us-east-1", bucket_name="test-bucket", include=[]
        )

        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        """Test include list with various values."""
        options = SingleBucketRequest(
            region="ap-southeast-1",
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
        options = SingleBucketRequest(region="us-west-2", bucket_name="test-bucket")

        assert isinstance(options, SingleBucketRequest)

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields."""
        options = SingleBucketRequest(region="us-west-2", bucket_name="my-test-bucket")

        assert options.region == "us-west-2"
        assert options.bucket_name == "my-test-bucket"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["GetBucketTaggingAction", "GetBucketEncryptionAction"]
        options = SingleBucketRequest(
            region="eu-west-1", bucket_name="production-bucket", include=include_list
        )

        assert options.region == "eu-west-1"
        assert options.bucket_name == "production-bucket"
        assert options.include == include_list

    def test_missing_bucket_name(self) -> None:
        """Test that missing bucket_name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleBucketRequest(region="us-west-2")  # type: ignore

        assert "bucket_name" in str(exc_info.value)

    def test_missing_region(self) -> None:
        """Test that missing region raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SingleBucketRequest(bucket_name="test-bucket")  # type: ignore

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
            options = SingleBucketRequest(region="us-west-2", bucket_name=bucket_name)
            assert options.bucket_name == bucket_name


class TestPaginatedS3BucketExporterOptions:
    """Test the PaginatedS3BucketExporterOptions class."""

    def test_inheritance(self) -> None:
        """Test that PaginatedS3BucketExporterOptions inherits from ExporterOptions."""
        options = PaginatedBucketRequest(region="us-west-2")

        assert isinstance(options, PaginatedBucketRequest)

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with only required fields."""
        options = PaginatedBucketRequest(region="us-east-1")

        assert options.region == "us-east-1"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        """Test initialization with include list."""
        include_list = ["GetBucketPublicAccessBlockAction", "GetBucketTaggingAction"]
        options = PaginatedBucketRequest(region="ap-southeast-2", include=include_list)

        assert options.region == "ap-southeast-2"
        assert options.include == include_list

    def test_no_additional_fields(self) -> None:
        """Test that PaginatedS3BucketExporterOptions doesn't add additional fields."""
        options = PaginatedBucketRequest(region="eu-north-1")

        # Should only have the fields from ExporterOptions
        assert hasattr(options, "region")
        assert hasattr(options, "include")
        assert not hasattr(options, "bucket_name")


class TestS3BucketProperties:
    """Test the S3BucketProperties model."""

    def test_initialization_empty(self) -> None:
        """Test initialization with no properties."""
        properties = BucketProperties()

        # All fields should be None initially
        assert properties.AccessControl is None
        assert properties.VersioningConfiguration is None
        assert properties.Tags is None
        assert properties.BucketEncryption is None
        assert properties.Name == ""  # Default empty string
        assert properties.PublicAccessBlockConfiguration is None

    def test_initialization_with_properties(self) -> None:
        """Test initialization with some properties."""
        properties = BucketProperties(
            Name="test-bucket",
            Tags=[{"Key": "Environment", "Value": "test"}],
            PublicAccessBlockConfiguration={"BlockPublicAcls": True},
        )

        assert properties.Name == "test-bucket"
        assert properties.Tags == [{"Key": "Environment", "Value": "test"}]
        assert properties.PublicAccessBlockConfiguration == {"BlockPublicAcls": True}

        # Non-specified fields should be None
        assert properties.AccessControl is None
        assert properties.VersioningConfiguration is None

    def test_dict_exclude_none(self) -> None:
        """Test dict() with exclude_none=True."""
        properties = BucketProperties(
            Name="test-bucket", Tags=[{"Key": "Project", "Value": "demo"}]
        )

        result = properties.dict(exclude_none=True)

        # Should only include non-None fields
        assert "Name" in result
        assert "Tags" in result
        assert result["Name"] == "test-bucket"
        assert result["Tags"] == [{"Key": "Project", "Value": "demo"}]

        # None fields should be excluded
        assert "AccessControl" not in result
        assert "VersioningConfiguration" not in result
        assert "BucketEncryption" not in result

    def test_all_properties_assignment(self) -> None:
        """Test assignment of all available properties."""
        properties = BucketProperties(
            AccessControl="Private",
            VersioningConfiguration={"Status": "Enabled"},
            Tags=[{"Key": "Owner", "Value": "team"}],
            BucketEncryption={"Rules": []},
            ReplicationConfiguration={
                "Role": "arn:aws:iam::123456789012:role/replication-role"
            },
            Location={"LocationConstraint": "us-west-2"},
            Policy={"Version": "2012-10-17"},
            BucketArn="arn:aws:s3:::test-bucket",
            RegionalDomainName="test-bucket.s3.us-west-2.amazonaws.com",
            DomainName="test-bucket.s3.amazonaws.com",
            DualStackDomainName="test-bucket.s3.dualstack.us-west-2.amazonaws.com",
            WebsiteURL="http://test-bucket.s3-website-us-west-2.amazonaws.com",
            Name="test-bucket",
            PublicAccessBlockConfiguration={"BlockPublicAcls": True},
            OwnershipControls={"Rules": []},
            CorsConfiguration={"CORSRules": []},
        )

        # Verify all properties are set
        assert properties.AccessControl == "Private"
        assert properties.VersioningConfiguration == {"Status": "Enabled"}
        assert properties.Tags == [{"Key": "Owner", "Value": "team"}]
        assert properties.BucketEncryption == {"Rules": []}
        assert properties.Name == "test-bucket"
        assert properties.BucketArn == "arn:aws:s3:::test-bucket"
        assert properties.PublicAccessBlockConfiguration == {"BlockPublicAcls": True}


class TestS3Bucket:
    """Test the S3Bucket model."""

    def test_initialization_with_identifier(self) -> None:
        """Test initialization with required identifier."""
        bucket = Bucket(Properties=BucketProperties(Name="test-bucket"))

        assert bucket.Type == "AWS::S3::Bucket"
        assert bucket.Properties.Name == "test-bucket"
        assert isinstance(bucket.Properties, BucketProperties)

    def test_initialization_with_properties(self) -> None:
        """Test initialization with custom properties."""
        properties = BucketProperties(
            Name="custom-bucket", Tags=[{"Key": "Team", "Value": "engineering"}]
        )
        bucket = Bucket(Properties=properties)

        assert bucket.Properties == properties
        assert bucket.Properties.Name == "custom-bucket"
        assert bucket.Properties.Tags == [{"Key": "Team", "Value": "engineering"}]

    def test_type_is_fixed(self) -> None:
        """Test that Type is always AWS::S3::Bucket."""
        bucket1 = Bucket(Properties=BucketProperties(Name="bucket1"))
        bucket2 = Bucket(Properties=BucketProperties(Name="bucket2"))

        assert bucket1.Type == "AWS::S3::Bucket"
        assert bucket2.Type == "AWS::S3::Bucket"

    def test_dict_exclude_none(self) -> None:
        """Test dict() with exclude_none=True."""
        properties = BucketProperties(Name="test-bucket")
        bucket = Bucket(Properties=properties)

        result = bucket.dict(exclude_none=True)

        assert "Type" in result
        assert "Properties" in result

        assert result["Type"] == "AWS::S3::Bucket"
        assert result["Properties"]["Name"] == "test-bucket"

    def test_properties_default_factory(self) -> None:
        """Test that Properties uses default factory."""
        bucket1 = Bucket(Properties=BucketProperties(Name="bucket1"))
        bucket2 = Bucket(Properties=BucketProperties(Name="bucket2"))

        # Should be different instances
        assert bucket1.Properties is not bucket2.Properties

        # But both should be BucketProperties instances
        assert isinstance(bucket1.Properties, BucketProperties)
        assert isinstance(bucket2.Properties, BucketProperties)

    def test_bucket_serialization_roundtrip(self) -> None:
        """Test that bucket can be serialized and deserialized."""
        original_bucket = Bucket(
            Properties=BucketProperties(
                Name="roundtrip-bucket",
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
        assert recreated_bucket.Properties.Name == original_bucket.Properties.Name
        assert recreated_bucket.Properties.Tags == original_bucket.Properties.Tags
        assert (
            recreated_bucket.Properties.BucketEncryption
            == original_bucket.Properties.BucketEncryption
        )
