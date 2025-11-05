import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from harbor.webhook_processors.artifact_processor import ArtifactWebhookProcessor
from harbor.webhook_processors.repository_processor import RepositoryWebhookProcessor
from harbor.webhook_processors.project_processor import ProjectWebhookProcessor
from harbor.helpers.webhook_utils import validate_webhook_signature, extract_resource_info


class TestWebhookUtils:
    """Test webhook utility functions."""
    
    def test_validate_webhook_signature_success(self):
        """Test successful webhook signature validation."""
        payload = b'{"test": "data"}'
        secret = "test_secret"
        
        import hmac
        import hashlib
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        signature = f"sha256={expected_signature}"
        
        assert validate_webhook_signature(payload, signature, secret) is True
    
    def test_validate_webhook_signature_failure(self):
        """Test failed webhook signature validation."""
        payload = b'{"test": "data"}'
        secret = "test_secret"
        signature = "sha256=invalid_signature"
        
        assert validate_webhook_signature(payload, signature, secret) is False
    
    def test_validate_webhook_signature_no_secret(self):
        """Test webhook validation with no secret (should pass)."""
        payload = b'{"test": "data"}'
        signature = "sha256=anything"
        
        assert validate_webhook_signature(payload, signature, None) is True
    
    def test_extract_resource_info(self, sample_webhook_event):
        """Test resource info extraction from webhook event."""
        resource_info = extract_resource_info(sample_webhook_event)
        
        assert resource_info["event_type"] == "PUSH_ARTIFACT"
        assert resource_info["project_name"] == "opensource"
        assert resource_info["repository_name"] == "nginx"
        assert resource_info["artifact_digest"] == "sha256:1234567890abcdef"
        assert resource_info["tag"] == "latest"


class TestArtifactWebhookProcessor:
    """Test Artifact webhook processor."""
    
    @pytest.fixture
    def processor(self):
        """Create artifact webhook processor for testing."""
        with patch('harbor.webhook_processors.base_processor.ocean') as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "http://localhost:8081",
                "username": "admin",
                "password": "Harbor12345",
                "webhook_secret": "test_secret"
            }
            return ArtifactWebhookProcessor()
    
    @pytest.mark.asyncio
    async def test_process_push_artifact_event(self, processor, sample_webhook_event, sample_artifact_data):
        """Test processing push artifact webhook event."""
        # Mock the client
        processor.client.get_paginated_artifacts = AsyncMock()
        
        async def mock_paginated_artifacts(project_name, repo_name, **filters):
            yield sample_artifact_data
            
        processor.client.get_paginated_artifacts = mock_paginated_artifacts
        
        # Mock webhook event
        webhook_event = MagicMock()
        webhook_event.body = json.dumps(sample_webhook_event).encode()
        webhook_event.body_json = sample_webhook_event
        webhook_event.headers = {"x-harbor-signature": "sha256=valid_signature"}
        
        # Mock signature validation
        with patch('harbor.webhook_processors.base_processor.validate_webhook_signature', return_value=True):
            result = await processor.process(webhook_event)
            
        assert len(result) == 1
        assert result[0]["project_name"] == "opensource"
        assert result[0]["repository_name"] == "nginx"
    
    @pytest.mark.asyncio
    async def test_process_delete_artifact_event(self, processor):
        """Test processing delete artifact webhook event."""
        delete_event = {
            "type": "DELETE_ARTIFACT",
            "event_data": {
                "project": {"name": "opensource"},
                "repository": {"name": "opensource/nginx"},
                "resources": [{"digest": "sha256:1234567890abcdef"}]
            }
        }
        
        webhook_event = MagicMock()
        webhook_event.body = json.dumps(delete_event).encode()
        webhook_event.body_json = delete_event
        webhook_event.headers = {"x-harbor-signature": "sha256=valid_signature"}
        
        with patch('harbor.webhook_processors.base_processor.validate_webhook_signature', return_value=True):
            result = await processor.process(webhook_event)
            
        # Delete events return empty list (artifact no longer exists)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_process_scan_completed_event(self, processor, sample_artifact_data):
        """Test processing scan completed webhook event."""
        scan_event = {
            "type": "SCANNING_COMPLETED",
            "event_data": {
                "project": {"name": "opensource"},
                "repository": {"name": "opensource/nginx"},
                "resources": [{"digest": "sha256:1234567890abcdef"}]
            }
        }
        
        # Mock the client with scan results
        async def mock_paginated_artifacts(project_name, repo_name, **filters):
            yield sample_artifact_data
            
        processor.client.get_paginated_artifacts = mock_paginated_artifacts
        
        webhook_event = MagicMock()
        webhook_event.body = json.dumps(scan_event).encode()
        webhook_event.body_json = scan_event
        webhook_event.headers = {"x-harbor-signature": "sha256=valid_signature"}
        
        with patch('harbor.webhook_processors.base_processor.validate_webhook_signature', return_value=True):
            result = await processor.process(webhook_event)
            
        assert len(result) == 1
        assert "scan_overview" in result[0]


class TestRepositoryWebhookProcessor:
    """Test Repository webhook processor."""
    
    @pytest.fixture
    def processor(self):
        """Create repository webhook processor for testing."""
        with patch('harbor.webhook_processors.base_processor.ocean') as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "http://localhost:8081",
                "username": "admin",
                "password": "Harbor12345",
                "webhook_secret": "test_secret"
            }
            return RepositoryWebhookProcessor()
    
    @pytest.mark.asyncio
    async def test_process_repository_update(self, processor, sample_repository_data):
        """Test processing repository update event."""
        push_event = {
            "type": "PUSH_ARTIFACT",
            "event_data": {
                "project": {"name": "opensource"},
                "repository": {"name": "opensource/nginx"}
            }
        }
        
        # Mock the client
        async def mock_paginated_repositories(project_name, **filters):
            yield sample_repository_data
            
        processor.client.get_paginated_repositories = mock_paginated_repositories
        
        webhook_event = MagicMock()
        webhook_event.body = json.dumps(push_event).encode()
        webhook_event.body_json = push_event
        webhook_event.headers = {"x-harbor-signature": "sha256=valid_signature"}
        
        with patch('harbor.webhook_processors.base_processor.validate_webhook_signature', return_value=True):
            result = await processor.process(webhook_event)
            
        assert len(result) == 2  # All repositories in project
        assert all(repo["project_name"] == "opensource" for repo in result)


class TestProjectWebhookProcessor:
    """Test Project webhook processor."""
    
    @pytest.fixture
    def processor(self):
        """Create project webhook processor for testing."""
        with patch('harbor.webhook_processors.base_processor.ocean') as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "http://localhost:8081",
                "username": "admin",
                "password": "Harbor12345",
                "webhook_secret": "test_secret"
            }
            return ProjectWebhookProcessor()
    
    @pytest.mark.asyncio
    async def test_process_quota_event(self, processor, sample_project_data):
        """Test processing project quota event."""
        quota_event = {
            "type": "PROJECT_QUOTA_EXCEED",
            "event_data": {
                "project": {"name": "opensource"}
            }
        }
        
        # Mock the client
        processor.client.get_projects = AsyncMock(return_value=[sample_project_data[1]])
        
        webhook_event = MagicMock()
        webhook_event.body = json.dumps(quota_event).encode()
        webhook_event.body_json = quota_event
        webhook_event.headers = {"x-harbor-signature": "sha256=valid_signature"}
        
        with patch('harbor.webhook_processors.base_processor.validate_webhook_signature', return_value=True):
            result = await processor.process(webhook_event)
            
        assert len(result) == 1
        assert result[0]["name"] == "opensource"


class TestWebhookSecurity:
    """Test webhook security features."""
    
    @pytest.mark.asyncio
    async def test_invalid_signature_rejection(self):
        """Test that invalid signatures are rejected."""
        with patch('harbor.webhook_processors.base_processor.ocean') as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "http://localhost:8081",
                "username": "admin",
                "password": "Harbor12345",
                "webhook_secret": "test_secret"
            }
            
            processor = ArtifactWebhookProcessor()
            
            webhook_event = MagicMock()
            webhook_event.body = b'{"test": "data"}'
            webhook_event.body_json = {"type": "PUSH_ARTIFACT"}
            webhook_event.headers = {"x-harbor-signature": "sha256=invalid_signature"}
            
            result = await processor.process(webhook_event)
            
            # Should return empty list due to invalid signature
            assert result == []
    
    @pytest.mark.asyncio
    async def test_missing_signature_with_secret(self):
        """Test behavior when signature is missing but secret is configured."""
        with patch('harbor.webhook_processors.base_processor.ocean') as mock_ocean:
            mock_ocean.integration_config = {
                "harbor_url": "http://localhost:8081",
                "username": "admin",
                "password": "Harbor12345",
                "webhook_secret": "test_secret"
            }
            
            processor = ArtifactWebhookProcessor()
            
            webhook_event = MagicMock()
            webhook_event.body = b'{"test": "data"}'
            webhook_event.body_json = {"type": "PUSH_ARTIFACT"}
            webhook_event.headers = {}  # No signature header
            
            result = await processor.process(webhook_event)
            
            # Should return empty list due to missing signature
            assert result == []