import base64
import pytest
from bit_bucket.bit_bucket_integration.auth import BasicAuth
def test_get_auth_token_valid():
    """Test valid username and password encoding."""
    username = "user"
    password = "password"
    expected_token = base64.b64encode(f"{username}:{password}".encode()).decode()

    token = BasicAuth().get_auth_token(username, password)

    assert isinstance(token, str)
    assert token == expected_token

def test_get_auth_token_empty_values():
    """Test handling of empty username or password."""
    with pytest.raises(ValueError):
        BasicAuth().get_auth_token("", "password")

    with pytest.raises(ValueError):
        BasicAuth().get_auth_token("user", "")

def test_get_auth_token_none_values():
    """Test handling of None as input."""
    with pytest.raises(TypeError):
        BasicAuth().get_auth_token(None, "password")

    with pytest.raises(TypeError):
        BasicAuth().get_auth_token("user", None)