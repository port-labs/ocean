import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from harbor.integration import HarborIntegration, HarborPortAppConfig


class TestHarborIntegration:
    """Test Harbor integration configuration and setup."""
    
    def test_harbor_port_app_config_validation(self):
        """Test Harbor configuration validation."""
        # Valid configuration
        config = HarborPortAppConfig(
            harbor_url="http://localhost:8081",
            username="admin",
            password="Harbor12345"
        )
        
        assert config.harbor_url == "http://localhost:8081"
        assert config.username == "admin"
        assert config.password == "Harbor12345"
        assert config.max_concurrent_requests == 10  # Default value
        assert config.verify_ssl is True  # Default value
    
    def test_harbor_port_app_config_with_advanced_settings(self):
        """Test Harbor configuration with advanced settings."""
        config = HarborPortAppConfig(
            harbor_url="https://harbor.company.com",
            username="robot$test",
            password="token123",
            max_concurrent_requests=20,
            request_timeout=60,
            rate_limit_delay=0.5,
            verify_ssl=False,
            webhook_secret="webhook_secret_123"
        )
        
        assert config.max_concurrent_requests == 20
        assert config.request_timeout == 60
        assert config.rate_limit_delay == 0.5
        assert config.verify_ssl is False
        assert config.webhook_secret == "webhook_secret_123"
    
    def test_harbor_integration_initialization(self):
        """Test Harbor integration initialization."""
        with patch('harbor.integration.PortOceanContext') as mock_context:
            integration = HarborIntegration(mock_context)
            assert integration is not None
            assert hasattr(integration, 'AppConfigHandlerClass')


class TestMainHandlers:
    """Test main resync handlers."""
    
    @pytest.fixture
    def mock_ocean_config(self):
        """Mock Ocean configuration."""
        return {
            "harbor_url": "http://localhost:8081",
            "username": "admin",
            "password": "Harbor12345",
            "resources": [
                {
                    "kind": "project",
                    "selector": {"visibility": "public"}
                },
                {
                    "kind": "user",
                    "selector": {"admin_only": True}
                },
                {
                    "kind": "repository",
                    "selector": {"project_name": "opensource"}
                },
                {
                    "kind": "artifact",
                    "selector": {"with_scan_results": True}
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_resync_projects_handler(self, mock_ocean_config, sample_project_data):
        """Test projects resync handler."""
        with patch('harbor.main.ocean') as mock_ocean:
            mock_ocean.integration_config = mock_ocean_config
            
            with patch('harbor.main.create_harbor_client') as mock_create_client:
                mock_client = MagicMock()
                mock_create_client.return_value = mock_client
                
                with patch('harbor.main.ProjectExporter') as mock_exporter_class:
                    mock_exporter = MagicMock()
                    mock_exporter_class.return_value = mock_exporter
                    
                    # Mock async generator
                    async def mock_get_resources(selector):
                        yield sample_project_data
                        
                    mock_exporter.get_paginated_resources = mock_get_resources
                    
                    # Import and test the handler
                    from harbor.main import resync_projects
                    
                    results = []
                    async for batch in resync_projects("project"):
                        results.extend(batch)
                    
                    assert len(results) == 2
                    assert results[0]["name"] == "library"
                    
                    # Verify selector was passed
                    mock_exporter.get_paginated_resources.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resync_users_handler(self, mock_ocean_config, sample_user_data):
        """Test users resync handler."""
        with patch('harbor.main.ocean') as mock_ocean:
            mock_ocean.integration_config = mock_ocean_config
            
            with patch('harbor.main.create_harbor_client') as mock_create_client:
                mock_client = MagicMock()
                mock_create_client.return_value = mock_client
                
                with patch('harbor.main.UserExporter') as mock_exporter_class:
                    mock_exporter = MagicMock()
                    mock_exporter_class.return_value = mock_exporter
                    
                    async def mock_get_resources(selector):
                        yield sample_user_data
                        
                    mock_exporter.get_paginated_resources = mock_get_resources
                    
                    from harbor.main import resync_users
                    
                    results = []
                    async for batch in resync_users("user"):
                        results.extend(batch)
                    
                    assert len(results) == 2
                    assert results[0]["username"] == "admin"
    
    @pytest.mark.asyncio
    async def test_resync_repositories_handler(self, mock_ocean_config, sample_repository_data):
        """Test repositories resync handler."""
        with patch('harbor.main.ocean') as mock_ocean:
            mock_ocean.integration_config = mock_ocean_config
            
            with patch('harbor.main.create_harbor_client') as mock_create_client:
                mock_client = MagicMock()
                mock_create_client.return_value = mock_client
                
                with patch('harbor.main.RepositoryExporter') as mock_exporter_class:
                    mock_exporter = MagicMock()
                    mock_exporter_class.return_value = mock_exporter
                    
                    async def mock_get_resources(selector):
                        yield sample_repository_data
                        
                    mock_exporter.get_paginated_resources = mock_get_resources
                    
                    from harbor.main import resync_repositories
                    
                    results = []
                    async for batch in resync_repositories("repository"):
                        results.extend(batch)
                    
                    assert len(results) == 2
                    assert results[0]["name"] == "opensource/nginx"
    
    @pytest.mark.asyncio
    async def test_resync_artifacts_handler(self, mock_ocean_config, sample_artifact_data):
        """Test artifacts resync handler."""
        with patch('harbor.main.ocean') as mock_ocean:
            mock_ocean.integration_config = mock_ocean_config
            
            with patch('harbor.main.create_harbor_client') as mock_create_client:
                mock_client = MagicMock()
                mock_create_client.return_value = mock_client
                
                with patch('harbor.main.ArtifactExporter') as mock_exporter_class:
                    mock_exporter = MagicMock()
                    mock_exporter_class.return_value = mock_exporter
                    
                    async def mock_get_resources(selector):
                        yield sample_artifact_data
                        
                    mock_exporter.get_paginated_resources = mock_get_resources
                    
                    from harbor.main import resync_artifacts
                    
                    results = []
                    async for batch in resync_artifacts("artifact"):
                        results.extend(batch)
                    
                    assert len(results) == 1
                    assert results[0]["digest"] == "sha256:1234567890abcdef"
    
    def test_get_selector_config(self, mock_ocean_config):
        """Test selector configuration extraction."""
        with patch('harbor.main.ocean') as mock_ocean:
            mock_ocean.integration_config = mock_ocean_config
            
            from harbor.main import get_selector_config
            
            project_selector = get_selector_config("project")
            assert project_selector == {"visibility": "public"}
            
            user_selector = get_selector_config("user")
            assert user_selector == {"admin_only": True}
            
            # Test non-existent kind
            unknown_selector = get_selector_config("unknown")
            assert unknown_selector == {}
    
    def test_create_harbor_client_with_config(self, mock_ocean_config):
        """Test Harbor client creation with configuration."""
        with patch('harbor.main.ocean') as mock_ocean:
            mock_ocean.integration_config = mock_ocean_config
            
            with patch('harbor.main.HarborClient') as mock_client_class:
                from harbor.main import create_harbor_client
                
                create_harbor_client()
                
                mock_client_class.assert_called_once_with(
                    base_url="http://localhost:8081",
                    username="admin",
                    password="Harbor12345",
                    max_concurrent_requests=10,  # Default
                    request_timeout=30,  # Default
                    rate_limit_delay=0.1,  # Default
                    verify_ssl=True  # Default
                )