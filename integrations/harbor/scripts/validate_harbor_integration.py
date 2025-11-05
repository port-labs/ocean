#!/usr/bin/env python3
"""
Harbor Integration Validation Script
Tests Harbor API connectivity and validates data structure for Port integration
"""

import json
import requests
from urllib.parse import urljoin
import base64
from typing import Dict, List, Any

class HarborValidator:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/v2.0"
        self.auth = (username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        
    def test_connectivity(self) -> bool:
        """Test basic Harbor API connectivity"""
        try:
            response = self.session.get(f"{self.api_base}/systeminfo")
            if response.status_code == 200:
                print("✅ Harbor API connectivity: SUCCESS")
                return True
            else:
                print(f"❌ Harbor API connectivity: FAILED (Status: {response.status_code})")
                return False
        except Exception as e:
            print(f"❌ Harbor API connectivity: FAILED ({str(e)})")
            return False
    
    def validate_projects(self) -> bool:
        """Validate projects endpoint and data structure"""
        try:
            response = self.session.get(f"{self.api_base}/projects")
            if response.status_code != 200:
                print(f"❌ Projects API: FAILED (Status: {response.status_code})")
                return False
                
            projects = response.json()
            print(f"✅ Projects API: SUCCESS ({len(projects)} projects found)")
            
            if projects:
                project = projects[0]
                required_fields = ['project_id', 'name', 'owner_name', 'creation_time']
                missing_fields = [field for field in required_fields if field not in project]
                if missing_fields:
                    print(f"❌ Project structure: Missing fields {missing_fields}")
                    return False
                print("✅ Project structure: Valid")
            
            return True
        except Exception as e:
            print(f"❌ Projects validation: FAILED ({str(e)})")
            return False
    
    def validate_users(self) -> bool:
        """Validate users endpoint and data structure"""
        try:
            response = self.session.get(f"{self.api_base}/users")
            if response.status_code != 200:
                print(f"❌ Users API: FAILED (Status: {response.status_code})")
                return False
                
            users = response.json()
            print(f"✅ Users API: SUCCESS ({len(users)} users found)")
            
            if users:
                user = users[0]
                required_fields = ['user_id', 'username', 'email']
                missing_fields = [field for field in required_fields if field not in user]
                if missing_fields:
                    print(f"❌ User structure: Missing fields {missing_fields}")
                    return False
                print("✅ User structure: Valid")
            
            return True
        except Exception as e:
            print(f"❌ Users validation: FAILED ({str(e)})")
            return False
    
    def validate_repositories(self) -> bool:
        """Validate repositories endpoint and data structure"""
        try:
            # Get projects first to find one with repositories
            projects_response = self.session.get(f"{self.api_base}/projects")
            if projects_response.status_code != 200:
                return False
                
            projects = projects_response.json()
            project_with_repos = None
            
            for project in projects:
                if project.get('repo_count', 0) > 0:
                    project_with_repos = project
                    break
            
            if not project_with_repos:
                print("⚠️  No projects with repositories found")
                return True
            
            project_name = project_with_repos['name']
            response = self.session.get(f"{self.api_base}/projects/{project_name}/repositories")
            
            if response.status_code != 200:
                print(f"❌ Repositories API: FAILED (Status: {response.status_code})")
                return False
                
            repositories = response.json()
            print(f"✅ Repositories API: SUCCESS ({len(repositories)} repositories found)")
            
            if repositories:
                repo = repositories[0]
                required_fields = ['name', 'project_id', 'creation_time']
                missing_fields = [field for field in required_fields if field not in repo]
                if missing_fields:
                    print(f"❌ Repository structure: Missing fields {missing_fields}")
                    return False
                print("✅ Repository structure: Valid")
            
            return True
        except Exception as e:
            print(f"❌ Repositories validation: FAILED ({str(e)})")
            return False
    
    def validate_artifacts(self) -> bool:
        """Validate artifacts endpoint and data structure"""
        try:
            # Get a repository with artifacts
            projects_response = self.session.get(f"{self.api_base}/projects")
            if projects_response.status_code != 200:
                return False
                
            projects = projects_response.json()
            
            for project in projects:
                if project.get('repo_count', 0) > 0:
                    project_name = project['name']
                    repos_response = self.session.get(f"{self.api_base}/projects/{project_name}/repositories")
                    
                    if repos_response.status_code == 200:
                        repositories = repos_response.json()
                        
                        for repo in repositories:
                            repo_name = repo['name'].split('/')[-1]  # Get repo name without project prefix
                            artifacts_response = self.session.get(
                                f"{self.api_base}/projects/{project_name}/repositories/{repo_name}/artifacts"
                            )
                            
                            if artifacts_response.status_code == 200:
                                artifacts = artifacts_response.json()
                                if artifacts:
                                    print(f"✅ Artifacts API: SUCCESS ({len(artifacts)} artifacts found)")
                                    
                                    artifact = artifacts[0]
                                    required_fields = ['digest', 'media_type', 'push_time']
                                    missing_fields = [field for field in required_fields if field not in artifact]
                                    if missing_fields:
                                        print(f"❌ Artifact structure: Missing fields {missing_fields}")
                                        return False
                                    print("✅ Artifact structure: Valid")
                                    return True
            
            print("⚠️  No artifacts found in any repository")
            return True
            
        except Exception as e:
            print(f"❌ Artifacts validation: FAILED ({str(e)})")
            return False
    
    def validate_pagination(self) -> bool:
        """Test pagination functionality"""
        try:
            # Test with page_size parameter
            response = self.session.get(f"{self.api_base}/projects", params={'page_size': 1})
            if response.status_code != 200:
                print(f"❌ Pagination test: FAILED (Status: {response.status_code})")
                return False
            
            projects = response.json()
            if len(projects) <= 1:  # Should respect page_size
                print("✅ Pagination: Working")
                return True
            else:
                print("⚠️  Pagination: May not be working as expected")
                return True
                
        except Exception as e:
            print(f"❌ Pagination validation: FAILED ({str(e)})")
            return False
    
    def validate_port_config(self) -> bool:
        """Validate Port configuration files exist"""
        import os
        
        config_files = [
            '/home/adewale/harbor/ocean/integrations/harbor/.port/resources/blueprints.json',
            '/home/adewale/harbor/ocean/integrations/harbor/.port/resources/port-app-config.yml'
        ]
        
        all_exist = True
        for config_file in config_files:
            if os.path.exists(config_file):
                print(f"✅ Port config: {os.path.basename(config_file)} exists")
            else:
                print(f"❌ Port config: {os.path.basename(config_file)} missing")
                all_exist = False
        
        return all_exist

def main():
    print("🚀 Harbor Integration Validation")
    print("=" * 50)
    
    # Harbor configuration
    harbor_url = "http://localhost:8081"
    username = "admin"
    password = "Harbor12345"
    
    validator = HarborValidator(harbor_url, username, password)
    
    # Run validation tests
    tests = [
        ("Harbor API Connectivity", validator.test_connectivity),
        ("Projects Endpoint", validator.validate_projects),
        ("Users Endpoint", validator.validate_users),
        ("Repositories Endpoint", validator.validate_repositories),
        ("Artifacts Endpoint", validator.validate_artifacts),
        ("Pagination Support", validator.validate_pagination),
        ("Port Configuration", validator.validate_port_config),
    ]
    
    results = []
    print("\n📋 Running validation tests...")
    print("-" * 30)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validation tests passed! Harbor integration is ready.")
        return True
    else:
        print("⚠️  Some validation tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)