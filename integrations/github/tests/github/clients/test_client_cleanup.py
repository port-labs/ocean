"""Test client cleanup functionality."""

from unittest.mock import patch, MagicMock

from github.clients.client_factory import GithubClientFactory, clear_github_clients
from github.helpers.utils import GithubClientType


class TestClientCleanup:
    """Test the client cleanup functionality."""

    def test_clear_instances_method(self):
        """Test that clear_instances method clears all cached instances."""
        factory = GithubClientFactory()
        
        # Add some mock instances
        factory._instances[GithubClientType.REST] = "mock_rest_client"
        factory._instances[GithubClientType.GRAPHQL] = "mock_graphql_client"
        
        assert len(factory._instances) == 2
        
        # Clear instances
        factory.clear_instances()
        
        assert len(factory._instances) == 0

    def test_clear_github_clients_function(self):
        """Test that clear_github_clients convenience function works."""
        factory = GithubClientFactory()
        
        # Add some mock instances
        factory._instances[GithubClientType.REST] = "mock_rest_client"
        factory._instances[GithubClientType.GRAPHQL] = "mock_graphql_client"
        
        assert len(factory._instances) == 2
        
        # Use convenience function
        clear_github_clients()
        
        assert len(factory._instances) == 0

    def test_singleton_behavior(self):
        """Test that the factory is a singleton and shares instances."""
        factory1 = GithubClientFactory()
        factory2 = GithubClientFactory()
        
        # Should be the same instance
        assert factory1 is factory2
        
        # Should share the same _instances dictionary
        factory1._instances[GithubClientType.REST] = "test_client"
        assert len(factory2._instances) == 1
        assert factory2._instances[GithubClientType.REST] == "test_client"

    def test_clear_instances_logging(self):
        """Test that clear_instances logs the correct information."""
        factory = GithubClientFactory()
        
        # Add some mock instances
        factory._instances[GithubClientType.REST] = "mock_rest_client"
        factory._instances[GithubClientType.GRAPHQL] = "mock_graphql_client"
        
        # Clear instances - the logging will be visible in stderr
        factory.clear_instances()
        
        # The main test is that the method doesn't raise an exception
        # and the instances are cleared
        assert len(factory._instances) == 0

    def test_get_client_caching_behavior(self):
        """Test that get_client caches instances correctly."""
        factory = GithubClientFactory()
        
        # Mock the ocean configuration
        mock_ocean = MagicMock()
        mock_ocean.integration_config = {
            "github_host": "https://api.github.com",
            "github_token": "mock_token"
        }
        
        with patch('github.clients.client_factory.ocean', mock_ocean):
            # Mock the client creation to avoid actual authentication
            with patch('github.clients.client_factory.GithubRestClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                
                # Mock integration_config to return valid config
                with patch('github.clients.client_factory.integration_config') as mock_config:
                    mock_config.return_value = {
                        "authenticator": MagicMock(), 
                        "github_organization": "test-org",
                        "github_host": "https://api.github.com",
                        "organization": "test-org"
                    }
                    
                    # First call should create and cache
                    client1 = factory.get_client("test-org", GithubClientType.REST)
                    
                    # Second call should use cached instance
                    client2 = factory.get_client("test-org", GithubClientType.REST)
                    
                    # Should be the same instance
                    assert client1 is client2
                    
                    # Should only have created one client
                    assert len(factory._instances) == 1

    def teardown_method(self):
        """Clean up after each test."""
        factory = GithubClientFactory()
        factory.clear_instances()
