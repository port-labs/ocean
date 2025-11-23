""" Constants for Harbor API integration

Please keep this file focused on constants only, and updated with
the latest Harbor API details.
"""
from enum import StrEnum

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1
DEFAULT_TIMEOUT = 30
MAX_CONCURRENT_REQUESTS = 10

API_VERSION = "v2.0"
ENDPOINTS = {
    # list endpoints
    "projects": "/projects",
    "users": "/users",
    "repositories": "/projects/{project_name}/repositories",
    "artifacts": "/projects/{project_name}/repositories/{repository_name}/artifacts",

    # system-level
    "system_info": "/systeminfo",
    "webhooks": "/projects/{project_name}/webhook/policies",

    # detail endpoints
    'get_project': "/projects/{project_name}",
    "get_repository": "/projects/{project_name}/repositories/{repository_name}",
    "get_artifact": "/projects/{project_name}/repositories/{repository_name}/artifacts/{reference}",
}

WEBHOOK_EVENTS = {
    "PUSH_ARTIFACT": "PUSH_ARTIFACT",
    "PULL_ARTIFACT": "PULL_ARTIFACT",
    "DELETE_ARTIFACT": "DELETE_ARTIFACT",
    "SCANNING_COMPLETED": "SCANNING_COMPLETED",
    "SCANNING_FAILED": "SCANNING_FAILED",
    "QUOTA_EXCEED": "QUOTA_EXCEED",
    "REPLICATION": "REPLICATION",
}

ARTIFACT_QUERY_PARAMS = {
    "with_tag": True,           # include tags
    "with_label": True,          # include labels
    "with_scan_overview": True,  # include vulnerability scans
    "with_signature": True,      # include signatures
    "with_immutable_status": True,
}

class HarborKind(StrEnum):
    PROJECT = "project"
    USER = "user"
    REPOSITORY = "repository"
    ARTIFACT = "artifact"
