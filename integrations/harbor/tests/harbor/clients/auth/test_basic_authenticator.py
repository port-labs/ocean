import base64
import pytest

from harbor.clients.auth.abstract_authenticator import HarborToken, HarborHeaders
from harbor.clients.auth.basic_authenticator import HarborBasicAuthenticator
from harbor.clients.auth.robot_authenticator import HarborRobotAuthenticator


class TestHarborBasicAuthenticator:
    @pytest.fixture
    def basic_auth(self) -> HarborBasicAuthenticator:
        """Fixture to create a HarborBasicAuthenticator instance."""
        return HarborBasicAuthenticator(
            username="testuser",
            password="testpass",
        )

    @pytest.mark.asyncio
    async def test_token_generation(self, basic_auth: HarborBasicAuthenticator) -> None:
        """Test that token is correctly generated as base64 encoded username:password."""
        token = await basic_auth.get_token()

        decoded = base64.b64decode(token.token).decode()
        assert decoded == "testuser:testpass"

    @pytest.mark.asyncio
    async def test_headers_generation(
        self, basic_auth: HarborBasicAuthenticator
    ) -> None:
        """Test that headers are correctly generated with Basic auth."""
        headers = await basic_auth.get_headers()

        assert headers.authorization.startswith("Basic ")
        assert headers.accept == "application/json"

        auth_token = headers.authorization.split(" ")[1]
        decoded = base64.b64decode(auth_token).decode()
        assert decoded == "testuser:testpass"

    @pytest.mark.asyncio
    async def test_token_caching(self, basic_auth: HarborBasicAuthenticator) -> None:
        """Test that token is cached and reused."""
        token1 = await basic_auth.get_token()
        token2 = await basic_auth.get_token()

        assert token1 is token2
        assert token1.token == token2.token

    @pytest.mark.asyncio
    async def test_headers_caching(self, basic_auth: HarborBasicAuthenticator) -> None:
        """Test that headers are consistent across calls."""
        headers1 = await basic_auth.get_headers()
        headers2 = await basic_auth.get_headers()

        assert headers1.authorization == headers2.authorization
        assert headers1.accept == headers2.accept

    def test_client_property(self, basic_auth: HarborBasicAuthenticator) -> None:
        """Test that client property returns configured HTTP client."""
        client = basic_auth.client

        assert client is not None
        assert hasattr(client, "request")


class TestHarborRobotAuthenticator:
    @pytest.fixture
    def robot_auth(self) -> HarborRobotAuthenticator:
        """Fixture to create a HarborRobotAuthenticator instance."""
        return HarborRobotAuthenticator(
            robot_name="test-robot",
            robot_token="test-robot-token",
        )


class TestHarborToken:
    def test_token_creation(self) -> None:
        """Test HarborToken creation."""
        token = HarborToken(token="test-token")

        assert token.token == "test-token"


class TestHarborHeaders:
    def test_headers_creation(self) -> None:
        """Test HarborHeaders creation."""
        headers = HarborHeaders(authorization="Basic dGVzdA==")

        assert headers.authorization == "Basic dGVzdA=="
        assert headers.accept == "application/json"

    def test_headers_as_dict(self) -> None:
        """Test headers conversion to dictionary."""
        headers = HarborHeaders(authorization="Basic dGVzdA==")
        headers_dict = headers.as_dict()

        assert headers_dict["Authorization"] == "Basic dGVzdA=="
        assert headers_dict["Accept"] == "application/json"
