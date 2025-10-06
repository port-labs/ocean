"""Pytest configuration for Okta integration tests"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_integration_config():
    """Mock integration config fixture"""
    return {
        "okta_domain": "dev-123456.okta.com",
        "okta_api_token": "test_api_token_12345"
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "id": "00u1234567890abcdef",
        "status": "ACTIVE",
        "created": "2023-01-15T09:00:00.000Z",
        "activated": "2023-01-15T09:05:00.000Z",
        "type": {
            "id": "otyfed6d6ztMOe3Ze0h7"
        },
        "profile": {
            "firstName": "John",
            "lastName": "Doe",
            "login": "john.doe@example.com",
            "email": "john.doe@example.com",
            "displayName": "John Doe",
            "department": "Engineering",
            "locale": "en_US",
            "manager": {
                "id": "00u0987654321fedcba"
            }
        }
    }


@pytest.fixture
def sample_group_data():
    """Sample group data for testing"""
    return {
        "id": "00g1234567890abcdef",
        "created": "2023-01-10T08:00:00.000Z",
        "lastUpdated": "2024-01-05T12:30:00.000Z",
        "lastMembershipUpdated": "2024-01-15T14:45:00.000Z",
        "type": "OKTA_GROUP",
        "profile": {
            "name": "Engineering",
            "description": "Engineering team members"
        }
    }


@pytest.fixture  
def sample_role_data():
    """Sample role data for testing"""
    return {
        "id": "ra1234567890abcdef",
        "label": "User Administrator",
        "type": "STANDARD",
        "status": "ACTIVE",
        "created": "2023-01-01T00:00:00.000Z",
        "description": "Allows management of users and groups"
    }


@pytest.fixture
def sample_application_data():
    """Sample application data for testing"""
    return {
        "id": "0oa1234567890abcdef",
        "name": "example_saml_app",
        "label": "Example SAML Application", 
        "status": "ACTIVE",
        "created": "2023-06-15T10:00:00.000Z",
        "lastUpdated": "2024-01-10T15:30:00.000Z",
        "signOnMode": "SAML_2_0",
        "features": ["PROVISIONING", "PUSH_NEW_USERS"]
    }