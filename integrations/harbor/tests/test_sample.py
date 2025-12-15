"""Sample test to verify test infrastructure is working."""


def test_example() -> None:
    """Basic test to verify pytest is configured correctly."""
    assert 1 == 1


def test_string_operations() -> None:
    """Test basic string operations."""
    harbor_url = "https://harbor.example.com"
    assert harbor_url.startswith("https://")
    assert "harbor" in harbor_url


def test_list_operations() -> None:
    """Test basic list operations."""
    artifacts = ["nginx:latest", "redis:alpine", "postgres:14"]
    assert len(artifacts) == 3
    assert "nginx:latest" in artifacts
