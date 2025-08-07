from typing import Any
import pytest

from aws.core.exporters.s3.bucket.builder import S3BucketBuilder
from aws.core.exporters.s3.bucket.models import S3Bucket, S3BucketProperties


class TestS3BucketBuilder:

    def test_initialization(self) -> None:
        """Test that the builder initializes correctly with bucket name."""
        builder = S3BucketBuilder("test-bucket")

        # Verify internal bucket is created properly
        assert builder._bucket.Type == "AWS::S3::Bucket"
        assert isinstance(builder._bucket.Properties, S3BucketProperties)

    def test_build_default_bucket(self) -> None:
        """Test building a bucket with no additional data."""
        builder = S3BucketBuilder("empty-bucket")

        result = builder.build()

        assert isinstance(result, S3Bucket)
        assert result.Type == "AWS::S3::Bucket"
        assert isinstance(result.Properties, S3BucketProperties)

        # Properties should be empty initially
        properties_dict = result.Properties.dict(exclude_none=True)
        assert len(properties_dict) == 0

    def test_with_data_single_property(self) -> None:
        """Test adding a single property to the bucket."""
        builder = S3BucketBuilder("test-bucket")

        data = {"BucketName": "test-bucket"}
        result_builder = builder.with_data(data)

        # Verify method returns self for chaining
        assert result_builder is builder

        # Verify data was added
        bucket = builder.build()
        assert bucket.Properties.BucketName == "test-bucket"

    def test_with_data_multiple_properties(self) -> None:
        """Test adding multiple properties to the bucket."""
        builder = S3BucketBuilder("multi-prop-bucket")

        data: dict[str, Any] = {
            "BucketName": "multi-prop-bucket",
            "Tags": [{"Key": "Environment", "Value": "test"}],
            "BucketEncryption": {
                "Rules": [
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            },
        }

        builder.with_data(data)
        bucket = builder.build()

        # Verify all properties were set
        assert bucket.Properties.BucketName == "multi-prop-bucket"
        assert bucket.Properties.Tags == [{"Key": "Environment", "Value": "test"}]
        assert bucket.Properties.BucketEncryption == {
            "Rules": [
                {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
            ]
        }

    def test_with_data_chaining(self) -> None:
        """Test chaining multiple with_data calls."""
        builder = S3BucketBuilder("chain-bucket")

        # Chain multiple with_data calls
        result = (
            builder.with_data({"BucketName": "chain-bucket"})
            .with_data({"Tags": [{"Key": "Project", "Value": "demo"}]})
            .with_data({"PublicAccessBlockConfiguration": {"BlockPublicAcls": True}})
        )

        # Verify chaining returns the builder
        assert result is builder

        # Verify all data was accumulated
        bucket = builder.build()
        assert bucket.Properties.BucketName == "chain-bucket"
        assert bucket.Properties.Tags == [{"Key": "Project", "Value": "demo"}]
        assert bucket.Properties.PublicAccessBlockConfiguration == {
            "BlockPublicAcls": True
        }

    def test_with_data_overwrite_property(self) -> None:
        """Test that later with_data calls overwrite previous values."""
        builder = S3BucketBuilder("overwrite-bucket")

        # Set initial tags
        builder.with_data({"Tags": [{"Key": "Environment", "Value": "dev"}]})

        # Overwrite with new tags
        builder.with_data({"Tags": [{"Key": "Environment", "Value": "prod"}]})

        bucket = builder.build()

        # Verify the latest value is kept
        assert bucket.Properties.Tags == [{"Key": "Environment", "Value": "prod"}]

    def test_with_data_none_values(self) -> None:
        """Test with_data handling None values."""
        builder = S3BucketBuilder("none-bucket")

        data: dict[str, Any] = {
            "BucketName": "none-bucket",
            "Tags": None,
            "BucketEncryption": {"Rules": []},
        }

        builder.with_data(data)
        bucket = builder.build()

        # Verify None values are set (Pydantic will handle exclude_none during serialization)
        assert bucket.Properties.BucketName == "none-bucket"
        assert bucket.Properties.Tags is None
        assert bucket.Properties.BucketEncryption == {"Rules": []}

    def test_with_data_complex_nested_structure(self) -> None:
        """Test with_data with complex nested AWS structures."""
        builder = S3BucketBuilder("complex-bucket")

        complex_data = {
            "BucketName": "complex-bucket",
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": {
                    "Rules": [
                        {
                            "ApplyServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "aws:kms",
                                "KMSMasterKeyID": "arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012",
                            },
                            "BucketKeyEnabled": True,
                        }
                    ]
                }
            },
            "VersioningConfiguration": {"Status": "Enabled", "MfaDelete": "Disabled"},
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        }

        builder.with_data(complex_data)
        bucket = builder.build()

        # Verify complex nested structure is preserved
        assert bucket.Properties.BucketName == "complex-bucket"
        assert bucket.Properties.BucketEncryption == complex_data["BucketEncryption"]
        assert (
            bucket.Properties.VersioningConfiguration
            == complex_data["VersioningConfiguration"]
        )
        assert (
            bucket.Properties.PublicAccessBlockConfiguration
            == complex_data["PublicAccessBlockConfiguration"]
        )

    def test_multiple_builds_same_instance(self) -> None:
        """Test that multiple build() calls return the same bucket instance."""
        builder = S3BucketBuilder("same-bucket")
        builder.with_data({"BucketName": "same-bucket"})

        bucket1 = builder.build()
        bucket2 = builder.build()

        # Should return the same instance
        assert bucket1 is bucket2
        assert bucket1.Properties.BucketName == "same-bucket"

    def test_build_after_modification(self) -> None:
        """Test that modifications after first build affect subsequent builds."""
        builder = S3BucketBuilder("modify-bucket")
        builder.with_data({"BucketName": "modify-bucket"})

        bucket1 = builder.build()
        assert bucket1.Properties.BucketName == "modify-bucket"
        assert bucket1.Properties.Tags is None

        # Modify builder and build again
        builder.with_data({"Tags": [{"Key": "Modified", "Value": "true"}]})
        bucket2 = builder.build()

        # Should be the same instance but with updated properties
        assert bucket1 is bucket2
        assert bucket2.Properties.BucketName == "modify-bucket"
        assert bucket2.Properties.Tags == [{"Key": "Modified", "Value": "true"}]

    def test_with_data_invalid_property_name(self) -> None:
        """Test with_data with property names not in S3BucketProperties model."""
        builder = S3BucketBuilder("invalid-prop-bucket")

        # This should raise an error since Pydantic doesn't allow invalid fields
        with pytest.raises(ValueError, match="object has no field"):
            builder.with_data({"NonExistentProperty": "some_value"})

    def test_builder_isolation(self) -> None:
        """Test that different builder instances are isolated."""
        builder1 = S3BucketBuilder("bucket1")
        builder2 = S3BucketBuilder("bucket2")

        builder1.with_data(
            {"BucketName": "bucket1", "Tags": [{"Key": "Builder", "Value": "1"}]}
        )
        builder2.with_data(
            {"BucketName": "bucket2", "Tags": [{"Key": "Builder", "Value": "2"}]}
        )

        bucket1 = builder1.build()
        bucket2 = builder2.build()

        # Verify buckets are independent
        assert bucket1.Properties.BucketName == "bucket1"
        assert bucket2.Properties.BucketName == "bucket2"
        assert bucket1.Properties.Tags == [{"Key": "Builder", "Value": "1"}]
        assert bucket2.Properties.Tags == [{"Key": "Builder", "Value": "2"}]
        assert bucket1 is not bucket2
