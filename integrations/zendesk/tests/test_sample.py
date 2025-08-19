"""
Sample tests for Zendesk integration

Basic smoke tests to ensure integration components work correctly.
Following Ocean testing patterns for integration testing.

Purpose: Provide basic integration validation tests
Expected output: Successful test execution for core integration functionality
"""

import pytest
from unittest.mock import patch, AsyncMock

from kinds import Kinds
from initialize_client import create_zendesk_client


class TestZendeskIntegration:
    """Basic integration tests"""
    
    def test_kinds_definition(self):
        """Test that all required kinds are defined"""
        assert hasattr(Kinds, 'TICKET')
        assert hasattr(Kinds, 'SIDE_CONVERSATION')
        assert hasattr(Kinds, 'USER')
        assert hasattr(Kinds, 'ORGANIZATION')
        
        assert Kinds.TICKET == "ticket"
        assert Kinds.SIDE_CONVERSATION == "side_conversation"
        assert Kinds.USER == "user"
        assert Kinds.ORGANIZATION == "organization"
    
    @patch('port_ocean.context.ocean.ocean')
    def test_create_zendesk_client_success(self, mock_ocean):
        """Test successful client creation"""
        # Mock integration config
        mock_ocean.integration_config.get.side_effect = lambda key, default=None: {
            "subdomain": "test-company",
            "email": "test@example.com",
            "api_token": "test-token-123",
            "timeout": 30
        }.get(key, default)
        
        client = create_zendesk_client()
        
        assert client.subdomain == "test-company"
        assert client.email == "test@example.com"
        assert client.api_token == "test-token-123"
    
    @patch('port_ocean.context.ocean.ocean')
    def test_create_zendesk_client_missing_config(self, mock_ocean):
        """Test client creation with missing configuration"""
        # Mock missing subdomain
        mock_ocean.integration_config.get.side_effect = lambda key, default=None: {
            "email": "test@example.com",
            "api_token": "test-token-123"
        }.get(key, default)
        
        with pytest.raises(ValueError, match="Zendesk subdomain is required"):
            create_zendesk_client()
    
    @patch('port_ocean.context.ocean.ocean')
    def test_create_zendesk_client_missing_email(self, mock_ocean):
        """Test client creation with missing email"""
        mock_ocean.integration_config.get.side_effect = lambda key, default=None: {
            "subdomain": "test-company",
            "api_token": "test-token-123"
        }.get(key, default)
        
        with pytest.raises(ValueError, match="Email is required for API token authentication"):
            create_zendesk_client()
    
    @patch('port_ocean.context.ocean.ocean')
    def test_create_zendesk_client_missing_token(self, mock_ocean):
        """Test client creation with missing API token"""
        mock_ocean.integration_config.get.side_effect = lambda key, default=None: {
            "subdomain": "test-company",
            "email": "test@example.com"
        }.get(key, default)
        
        with pytest.raises(ValueError, match="API token is required"):
            create_zendesk_client()