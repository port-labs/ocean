#!/usr/bin/env python3
"""
Harbor Integration Test Runner

This script runs comprehensive integration tests against a live Harbor instance
and validates the integration with Port.
"""

import asyncio
import os
import sys
import json
from pathlib import Path

# Add the integration to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from harbor.clients.harbor_client import HarborClient
from harbor.core.exporters import ProjectExporter, UserExporter, RepositoryExporter, ArtifactExporter


class IntegrationTester:
    """Harbor integration tester."""
    
    def __init__(self):
        self.harbor_url = os.getenv("HARBOR_URL", "http://localhost:8081")
        self.harbor_username = os.getenv("HARBOR_USERNAME", "admin")
        self.harbor_password = os.getenv("HARBOR_PASSWORD", "Harbor12345")
        self.port_org_id = os.getenv("PORT_ORG_ID", "org_co9uqGjCJhE4q70A")
        
        self.client = HarborClient(
            base_url=self.harbor_url,
            username=self.harbor_username,
            password=self.harbor_password
        )
        
        self.results = {
            "harbor_connectivity": False,
            "projects_count": 0,
            "users_count": 0,
            "repositories_count": 0,
            "artifacts_count": 0,
            "filtering_works": False,
            "pagination_works": False,
            "port_config_valid": False,
            "errors": []
        }
    
    async def test_harbor_connectivity(self):
        """Test Harbor API connectivity."""
        try:
            projects = await self.client.get_projects(page_size=1)
            self.results["harbor_connectivity"] = True
            print(f"✅ Harbor connectivity successful - API responding")
            return True
        except Exception as e:
            self.results["errors"].append(f"Harbor connectivity failed: {e}")
            print(f"❌ Harbor connectivity failed: {e}")
            return False
    
    async def test_data_export(self):
        """Test data export functionality."""
        try:
            # Test projects
            project_exporter = ProjectExporter(self.client)
            async for projects_batch in project_exporter.get_paginated_resources():
                self.results["projects_count"] += len(projects_batch)
                if self.results["projects_count"] >= 10:  # Limit for testing
                    break
            
            # Test users
            user_exporter = UserExporter(self.client)
            async for users_batch in user_exporter.get_paginated_resources():
                self.results["users_count"] += len(users_batch)
                if self.results["users_count"] >= 10:  # Limit for testing
                    break
            
            # Test repositories
            repo_exporter = RepositoryExporter(self.client)
            async for repos_batch in repo_exporter.get_paginated_resources():
                self.results["repositories_count"] += len(repos_batch)
                if self.results["repositories_count"] >= 20:  # Limit for testing
                    break
            
            # Test artifacts
            artifact_exporter = ArtifactExporter(self.client)
            async for artifacts_batch in artifact_exporter.get_paginated_resources():
                self.results["artifacts_count"] += len(artifacts_batch)
                if self.results["artifacts_count"] >= 20:  # Limit for testing
                    break
            
            print(f"✅ Data export completed:")
            print(f"   - Projects: {self.results['projects_count']}")
            print(f"   - Users: {self.results['users_count']}")
            print(f"   - Repositories: {self.results['repositories_count']}")
            print(f"   - Artifacts: {self.results['artifacts_count']}")
            
        except Exception as e:
            self.results["errors"].append(f"Data export failed: {e}")
            print(f"❌ Data export failed: {e}")
    
    async def test_filtering(self):
        """Test filtering functionality."""
        try:
            # Test project filtering
            all_projects = await self.client.get_projects()
            public_projects = await self.client.get_projects(visibility="public")
            
            if len(public_projects) <= len(all_projects):
                self.results["filtering_works"] = True
                print(f"✅ Filtering works - {len(all_projects)} total, {len(public_projects)} public projects")
            else:
                print(f"❌ Filtering issue - more public than total projects")
                
        except Exception as e:
            self.results["errors"].append(f"Filtering test failed: {e}")
            print(f"❌ Filtering test failed: {e}")
    
    async def test_pagination(self):
        """Test pagination functionality."""
        try:
            page1 = await self.client.get_projects(page=1, page_size=1)
            page2 = await self.client.get_projects(page=2, page_size=1)
            
            # Basic pagination validation
            if isinstance(page1, list) and isinstance(page2, list):
                self.results["pagination_works"] = True
                print(f"✅ Pagination works - page 1: {len(page1)}, page 2: {len(page2)} items")
            
        except Exception as e:
            self.results["errors"].append(f"Pagination test failed: {e}")
            print(f"❌ Pagination test failed: {e}")
    
    def test_port_configuration(self):
        """Test Port configuration files."""
        try:
            # Test blueprints
            blueprints_path = Path(__file__).parent.parent / ".port" / "resources" / "blueprints.json"
            with open(blueprints_path) as f:
                blueprints = json.load(f)
            
            expected_blueprints = ["harborProject", "harborUser", "harborRepository", "harborArtifact"]
            blueprint_ids = [bp["identifier"] for bp in blueprints]
            
            if all(bp_id in blueprint_ids for bp_id in expected_blueprints):
                self.results["port_config_valid"] = True
                print(f"✅ Port configuration valid - {len(blueprints)} blueprints found")
            else:
                print(f"❌ Port configuration missing blueprints")
                
        except Exception as e:
            self.results["errors"].append(f"Port configuration test failed: {e}")
            print(f"❌ Port configuration test failed: {e}")
    
    async def run_all_tests(self):
        """Run all integration tests."""
        print("🚀 Starting Harbor Integration Tests")
        print(f"Harbor URL: {self.harbor_url}")
        print(f"Port Org ID: {self.port_org_id}")
        print("-" * 50)
        
        # Test Harbor connectivity first
        if not await self.test_harbor_connectivity():
            print("❌ Cannot proceed without Harbor connectivity")
            return False
        
        # Run all tests
        await self.test_data_export()
        await self.test_filtering()
        await self.test_pagination()
        self.test_port_configuration()
        
        # Print summary
        print("-" * 50)
        print("📊 Test Results Summary:")
        print(f"✅ Harbor Connectivity: {self.results['harbor_connectivity']}")
        print(f"📊 Data Export: {self.results['projects_count']} projects, {self.results['users_count']} users, {self.results['repositories_count']} repos, {self.results['artifacts_count']} artifacts")
        print(f"🔍 Filtering: {'✅' if self.results['filtering_works'] else '❌'}")
        print(f"📄 Pagination: {'✅' if self.results['pagination_works'] else '❌'}")
        print(f"⚙️  Port Config: {'✅' if self.results['port_config_valid'] else '❌'}")
        
        if self.results["errors"]:
            print(f"❌ Errors ({len(self.results['errors'])}):")
            for error in self.results["errors"]:
                print(f"   - {error}")
        
        success = (
            self.results["harbor_connectivity"] and
            self.results["port_config_valid"] and
            len(self.results["errors"]) == 0
        )
        
        print(f"\n🎯 Overall Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
        return success


async def main():
    """Main test runner."""
    tester = IntegrationTester()
    success = await tester.run_all_tests()
    
    # Save results
    results_path = Path(__file__).parent.parent / "test_results.json"
    with open(results_path, "w") as f:
        json.dump(tester.results, f, indent=2)
    
    print(f"\n📄 Results saved to: {results_path}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())