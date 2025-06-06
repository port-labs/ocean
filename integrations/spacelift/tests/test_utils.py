"""Tests for Spacelift utils."""

from spacelift.utils import ResourceKind, normalize_spacelift_resource, get_resource_url


class TestResourceKind:
    """Test suite for ResourceKind enum."""

    def test_resource_kind_values(self):
        """Test ResourceKind enum values."""
        assert ResourceKind.SPACE == "space"
        assert ResourceKind.STACK == "stack"
        assert ResourceKind.DEPLOYMENT == "deployment"
        assert ResourceKind.POLICY == "policy"
        assert ResourceKind.USER == "user"

    def test_resource_kind_membership(self):
        """Test ResourceKind enum membership."""
        assert "space" in ResourceKind
        assert "stack" in ResourceKind
        assert "deployment" in ResourceKind
        assert "policy" in ResourceKind
        assert "user" in ResourceKind
        assert "invalid" not in ResourceKind


class TestNormalizeSpaceliftResource:
    """Test suite for normalize_spacelift_resource function."""

    def test_normalize_basic_resource(self):
        """Test basic resource normalization."""
        resource = {
            "id": "test-id",
            "name": "Test Resource",
            "description": "A test resource",
        }

        normalized = normalize_spacelift_resource(resource, ResourceKind.SPACE)

        assert normalized["id"] == "test-id"
        assert normalized["name"] == "Test Resource"
        assert normalized["description"] == "A test resource"
        assert normalized["__resource_type"] == ResourceKind.SPACE

    def test_normalize_timestamps_integer(self):
        """Test timestamp normalization with integer values."""
        resource = {
            "id": "test-id",
            "createdAt": 1609459200,  # 2021-01-01 00:00:00 UTC
            "updatedAt": 1609459260,  # 2021-01-01 00:01:00 UTC
            "lastSeenAt": 1609459320,  # 2021-01-01 00:02:00 UTC
        }

        normalized = normalize_spacelift_resource(resource, ResourceKind.USER)

        assert normalized["createdAt"] == 1609459200
        assert normalized["updatedAt"] == 1609459260
        assert normalized["lastSeenAt"] == 1609459320

    def test_normalize_timestamps_float(self):
        """Test timestamp normalization with float values."""
        resource = {
            "id": "test-id",
            "createdAt": 1609459200.5,
            "updatedAt": 1609459260.123,
        }

        normalized = normalize_spacelift_resource(resource, ResourceKind.STACK)

        assert normalized["createdAt"] == 1609459200
        assert normalized["updatedAt"] == 1609459260

    def test_normalize_timestamps_none(self):
        """Test timestamp normalization with None values."""
        resource = {
            "id": "test-id",
            "createdAt": None,
            "updatedAt": None,
            "lastSeenAt": None,
        }

        normalized = normalize_spacelift_resource(resource, ResourceKind.POLICY)

        assert normalized["createdAt"] is None
        assert normalized["updatedAt"] is None
        assert normalized["lastSeenAt"] is None

    def test_normalize_labels_none(self):
        """Test label normalization with None value."""
        resource = {"id": "test-id", "labels": None}

        normalized = normalize_spacelift_resource(resource, ResourceKind.SPACE)

        assert normalized["labels"] == []

    def test_normalize_labels_string(self):
        """Test label normalization with string value."""
        resource = {"id": "test-id", "labels": "single-label"}

        normalized = normalize_spacelift_resource(resource, ResourceKind.STACK)

        assert normalized["labels"] == ["single-label"]

    def test_normalize_labels_list(self):
        """Test label normalization with list value."""
        resource = {"id": "test-id", "labels": ["label1", "label2", "label3"]}

        normalized = normalize_spacelift_resource(resource, ResourceKind.POLICY)

        assert normalized["labels"] == ["label1", "label2", "label3"]

    def test_normalize_labels_missing(self):
        """Test label normalization when labels field is missing."""
        resource = {"id": "test-id", "name": "Test Resource"}

        normalized = normalize_spacelift_resource(resource, ResourceKind.DEPLOYMENT)

        # Labels field should remain missing if not present
        assert "labels" not in normalized

    def test_normalize_preserves_original(self):
        """Test that normalization doesn't modify original resource."""
        original_resource = {"id": "test-id", "labels": None, "createdAt": 1609459200.5}
        original_copy = original_resource.copy()

        normalized = normalize_spacelift_resource(original_resource, ResourceKind.SPACE)

        # Original should be unchanged
        assert original_resource == original_copy
        # Normalized should be different
        assert normalized["labels"] == []
        assert normalized["createdAt"] == 1609459200
        assert normalized["__resource_type"] == ResourceKind.SPACE

    def test_normalize_complex_resource(self):
        """Test normalization of a complex resource with all field types."""
        resource = {
            "id": "complex-resource",
            "name": "Complex Resource",
            "labels": "single-label",
            "createdAt": 1609459200.123,
            "updatedAt": None,
            "lastSeenAt": 1609459260,
            "customField": "preserved",
            "nestedObject": {"field": "value"},
        }

        normalized = normalize_spacelift_resource(resource, ResourceKind.STACK)

        assert normalized["id"] == "complex-resource"
        assert normalized["name"] == "Complex Resource"
        assert normalized["labels"] == ["single-label"]
        assert normalized["createdAt"] == 1609459200
        assert normalized["updatedAt"] is None
        assert normalized["lastSeenAt"] == 1609459260
        assert normalized["customField"] == "preserved"
        assert normalized["nestedObject"] == {"field": "value"}
        assert normalized["__resource_type"] == ResourceKind.STACK


class TestGetResourceUrl:
    """Test suite for get_resource_url function."""

    def test_space_url(self):
        """Test URL generation for space resource."""
        resource = {"id": "space-123", "__resource_type": ResourceKind.SPACE}

        url = get_resource_url(resource, "mycompany")

        assert url == "https://mycompany.app.spacelift.io/spaces/space-123"

    def test_stack_url(self):
        """Test URL generation for stack resource."""
        resource = {"id": "stack-456", "__resource_type": ResourceKind.STACK}

        url = get_resource_url(resource, "testorg")

        assert url == "https://testorg.app.spacelift.io/stack/stack-456"

    def test_deployment_url(self):
        """Test URL generation for deployment resource."""
        resource = {
            "id": "run-789",
            "__resource_type": ResourceKind.DEPLOYMENT,
            "stack": {"id": "stack-123"},
        }

        url = get_resource_url(resource, "mycompany")

        assert url == "https://mycompany.app.spacelift.io/stack/stack-123/run/run-789"

    def test_deployment_url_missing_stack(self):
        """Test URL generation for deployment resource without stack info."""
        resource = {"id": "run-789", "__resource_type": ResourceKind.DEPLOYMENT}

        url = get_resource_url(resource, "mycompany")

        assert url == "https://mycompany.app.spacelift.io/stack//run/run-789"

    def test_policy_url(self):
        """Test URL generation for policy resource."""
        resource = {"id": "policy-101", "__resource_type": ResourceKind.POLICY}

        url = get_resource_url(resource, "example")

        assert url == "https://example.app.spacelift.io/policy/policy-101"

    def test_user_url(self):
        """Test URL generation for user resource."""
        resource = {"id": "user-202", "__resource_type": ResourceKind.USER}

        url = get_resource_url(resource, "company")

        assert url == "https://company.app.spacelift.io/users"

    def test_unknown_resource_type(self):
        """Test URL generation for unknown resource type."""
        resource = {"id": "unknown-303", "__resource_type": "unknown"}

        url = get_resource_url(resource, "mycompany")

        assert url == "https://mycompany.app.spacelift.io"

    def test_missing_resource_type(self):
        """Test URL generation when resource type is missing."""
        resource = {"id": "resource-404"}

        url = get_resource_url(resource, "mycompany")

        assert url == "https://mycompany.app.spacelift.io"

    def test_missing_resource_id(self):
        """Test URL generation when resource ID is missing."""
        resource = {"__resource_type": ResourceKind.SPACE}

        url = get_resource_url(resource, "mycompany")

        assert url == "https://mycompany.app.spacelift.io/spaces/"

    def test_empty_account_name(self):
        """Test URL generation with empty account name."""
        resource = {"id": "space-123", "__resource_type": ResourceKind.SPACE}

        url = get_resource_url(resource, "")

        assert url == "https://.app.spacelift.io/spaces/space-123"

    def test_different_account_names(self):
        """Test URL generation with different account names."""
        resource = {"id": "stack-456", "__resource_type": ResourceKind.STACK}

        url1 = get_resource_url(resource, "company-a")
        url2 = get_resource_url(resource, "company-b")

        assert url1 == "https://company-a.app.spacelift.io/stack/stack-456"
        assert url2 == "https://company-b.app.spacelift.io/stack/stack-456"
