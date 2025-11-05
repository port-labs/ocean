import pytest
import asyncio
import os
from typing import Dict, Any
from harbor.clients.harbor_client import HarborClient
from harbor.core.exporters import ProjectExporter, UserExporter, RepositoryExporter, ArtifactExporter


@pytest.mark.integration
class TestE2EIntegration:
    """End-to-end integration tests against live Harbor instance."""
    
    @pytest.fixture(scope="class")
    def harbor_config(self):
        """Harbor configuration for testing."""
        return {
            "base_url": os.getenv("HARBOR_URL", "http://localhost:8081"),
            "username": os.getenv("HARBOR_USERNAME", "admin"),
            "password": os.getenv("HARBOR_PASSWORD", "Harbor12345")
        }
    
    @pytest.fixture(scope="class")
    def harbor_client(self, harbor_config):
        """Create Harbor client for live testing."""
        return HarborClient(**harbor_config)
    
    @pytest.mark.asyncio
    async def test_harbor_connectivity(self, harbor_client):
        """Test basic Harbor connectivity."""
        try:
            projects = await harbor_client.get_projects(page_size=1)
            assert isinstance(projects, list)
            print(f"✅ Harbor connectivity verified - found {len(projects)} projects")
        except Exception as e:
            pytest.fail(f"❌ Harbor connectivity failed: {e}")
    
    @pytest.mark.asyncio
    async def test_projects_export(self, harbor_client):
        """Test projects export functionality."""
        exporter = ProjectExporter(harbor_client)
        
        projects_count = 0
        async for projects_batch in exporter.get_paginated_resources():
            projects_count += len(projects_batch)
            
            # Validate project structure
            for project in projects_batch:
                assert "name" in project
                assert "project_id" in project
                assert "creation_time" in project
                
        print(f"✅ Projects export completed - {projects_count} projects processed")
        assert projects_count > 0, "No projects found in Harbor"
    
    @pytest.mark.asyncio
    async def test_users_export(self, harbor_client):
        """Test users export functionality."""
        exporter = UserExporter(harbor_client)
        
        users_count = 0
        async for users_batch in exporter.get_paginated_resources():
            users_count += len(users_batch)
            
            # Validate user structure
            for user in users_batch:
                assert "username" in user
                assert "user_id" in user
                
        print(f"✅ Users export completed - {users_count} users processed")
        assert users_count > 0, "No users found in Harbor"
    
    @pytest.mark.asyncio
    async def test_repositories_export(self, harbor_client):
        """Test repositories export functionality."""
        exporter = RepositoryExporter(harbor_client)
        
        repositories_count = 0
        async for repos_batch in exporter.get_paginated_resources():
            repositories_count += len(repos_batch)
            
            # Validate repository structure
            for repo in repos_batch:
                assert "name" in repo
                assert "project_name" in repo
                assert "artifact_count" in repo
                
        print(f"✅ Repositories export completed - {repositories_count} repositories processed")
        # Note: May be 0 if no repositories exist
    
    @pytest.mark.asyncio
    async def test_artifacts_export(self, harbor_client):
        """Test artifacts export functionality."""
        exporter = ArtifactExporter(harbor_client)
        
        artifacts_count = 0
        async for artifacts_batch in exporter.get_paginated_resources():
            artifacts_count += len(artifacts_batch)
            
            # Validate artifact structure
            for artifact in artifacts_batch:
                assert "digest" in artifact
                assert "project_name" in artifact
                assert "repository_name" in artifact
                
        print(f"✅ Artifacts export completed - {artifacts_count} artifacts processed")
        # Note: May be 0 if no artifacts exist
    
    @pytest.mark.asyncio
    async def test_filtering_functionality(self, harbor_client):
        """Test filtering functionality."""
        # Test project filtering
        all_projects = await harbor_client.get_projects()
        public_projects = await harbor_client.get_projects(visibility="public")
        
        assert len(public_projects) <= len(all_projects)
        print(f"✅ Project filtering verified - {len(all_projects)} total, {len(public_projects)} public")
        
        # Test user filtering
        all_users = await harbor_client.get_users()
        admin_users = await harbor_client.get_users(admin_only=True)
        
        assert len(admin_users) <= len(all_users)
        print(f"✅ User filtering verified - {len(all_users)} total, {len(admin_users)} admin")
    
    @pytest.mark.asyncio
    async def test_pagination(self, harbor_client):
        """Test pagination functionality."""
        # Test with small page size
        page1 = await harbor_client.get_projects(page=1, page_size=1)
        page2 = await harbor_client.get_projects(page=2, page_size=1)
        
        # If we have more than 1 project, pages should be different
        if len(page1) == 1 and len(page2) == 1:
            assert page1[0]["project_id"] != page2[0]["project_id"]
            
        print(f"✅ Pagination verified - page 1: {len(page1)} items, page 2: {len(page2)} items")
    
    @pytest.mark.asyncio
    async def test_parallel_processing(self, harbor_client):
        """Test parallel processing capabilities."""
        import time
        
        # Sequential processing
        start_time = time.time()
        projects1 = await harbor_client.get_projects()
        projects2 = await harbor_client.get_projects()
        sequential_time = time.time() - start_time
        
        # Parallel processing
        start_time = time.time()
        results = await asyncio.gather(
            harbor_client.get_projects(),
            harbor_client.get_projects()
        )
        parallel_time = time.time() - start_time
        
        # Parallel should be faster (or at least not significantly slower)
        assert parallel_time <= sequential_time * 1.5
        print(f"✅ Parallel processing verified - sequential: {sequential_time:.2f}s, parallel: {parallel_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_error_handling(self, harbor_client):
        """Test error handling for invalid requests."""
        # Test invalid project name
        try:
            await harbor_client.get_repositories("nonexistent_project_12345")
            # If no error, that's fine (empty result)
            print("✅ Error handling verified - graceful handling of nonexistent project")
        except Exception as e:
            # Should handle errors gracefully
            assert "404" in str(e) or "not found" in str(e).lower()
            print(f"✅ Error handling verified - proper 404 handling: {e}")


@pytest.mark.integration
class TestPortIntegration:
    """Test Port integration functionality."""
    
    def test_port_configuration(self):
        """Test Port configuration structure."""
        port_org_id = os.getenv("PORT_ORG_ID", "org_co9uqGjCJhE4q70A")
        assert port_org_id.startswith("org_"), f"Invalid Port org ID format: {port_org_id}"
        print(f"✅ Port configuration verified - Org ID: {port_org_id}")
    
    def test_blueprint_structure(self):
        """Test blueprint JSON structure."""
        import json
        
        with open("/home/adewale/harbor/ocean/integrations/harbor/.port/resources/blueprints.json", "r") as f:
            blueprints = json.load(f)
            
        expected_blueprints = ["harborProject", "harborUser", "harborRepository", "harborArtifact"]
        
        blueprint_ids = [bp["identifier"] for bp in blueprints]
        for expected in expected_blueprints:
            assert expected in blueprint_ids, f"Missing blueprint: {expected}"
            
        print(f"✅ Blueprint structure verified - {len(blueprints)} blueprints found")
    
    def test_port_app_config(self):
        """Test Port app configuration."""
        import yaml
        
        with open("/home/adewale/harbor/ocean/integrations/harbor/.port/resources/port-app-config.yaml", "r") as f:
            config = yaml.safe_load(f)
            
        assert "resources" in config
        resource_kinds = [r["kind"] for r in config["resources"]]
        expected_kinds = ["project", "user", "repository", "artifact"]
        
        for kind in expected_kinds:
            assert kind in resource_kinds, f"Missing resource kind: {kind}"
            
        print(f"✅ Port app config verified - {len(resource_kinds)} resource types configured")


@pytest.mark.integration
class TestWebhookIntegration:
    """Test webhook integration functionality."""
    
    def test_webhook_signature_validation(self):
        """Test webhook signature validation."""
        from harbor.helpers.webhook_utils import validate_webhook_signature
        
        payload = b'{"test": "webhook"}'
        secret = "test_secret"
        
        # Test valid signature
        import hmac
        import hashlib
        valid_sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert validate_webhook_signature(payload, valid_sig, secret)
        
        # Test invalid signature
        invalid_sig = "sha256=invalid"
        assert not validate_webhook_signature(payload, invalid_sig, secret)
        
        print("✅ Webhook signature validation verified")
    
    def test_webhook_event_parsing(self):
        """Test webhook event parsing."""
        from harbor.helpers.webhook_utils import extract_resource_info
        
        sample_event = {
            "type": "PUSH_ARTIFACT",
            "event_data": {
                "project": {"name": "test-project"},
                "repository": {"name": "test-project/test-repo"},
                "resources": [{"digest": "sha256:abc123", "tag": "latest"}]
            }
        }
        
        info = extract_resource_info(sample_event)
        assert info["event_type"] == "PUSH_ARTIFACT"
        assert info["project_name"] == "test-project"
        assert info["repository_name"] == "test-repo"
        
        print("✅ Webhook event parsing verified")


if __name__ == "__main__":
    # Run integration tests
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short"
    ])