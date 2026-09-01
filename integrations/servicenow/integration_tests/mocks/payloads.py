from typing import Any

# Instance the tests pretend to talk to. Basic auth is used so no auth HTTP
# round-trip is needed — the authenticator just builds an Authorization header.
SERVICENOW_URL = "https://dev-testing.service-now.com"
SERVICENOW_USERNAME = "test-user"
SERVICENOW_PASSWORD = "test-password"

# Two records per table so the count assertions are meaningful.
RECORD_COUNT = 2


def sys_id(prefix: str, idx: int) -> str:
    return f"{prefix}-sys-id-{idx}"


def created_on(idx: int) -> str:
    """ServiceNow returns timestamps as 'YYYY-MM-DD HH:MM:SS'."""
    return f"2024-01-1{idx} 10:0{idx}:00"


def created_on_iso(idx: int) -> str:
    """What the mapping's strptime/strftime transform should produce."""
    return f"2024-01-1{idx}T10:0{idx}:00Z"


def user_group_response(idx: int) -> dict[str, Any]:
    return {
        "sys_id": sys_id("group", idx),
        "name": f"Group {idx}",
        "description": f"Description for group {idx}",
        "active": "true",
        "sys_created_on": created_on(idx),
        "sys_created_by": f"admin-{idx}",
    }


def service_catalog_response(idx: int) -> dict[str, Any]:
    return {
        "sys_id": sys_id("catalog", idx),
        "title": f"Catalog {idx}",
        "description": f"Description for catalog {idx}",
        "active": "true",
        "sys_created_on": created_on(idx),
        "sys_created_by": f"admin-{idx}",
    }


def incident_response(idx: int) -> dict[str, Any]:
    return {
        "sys_id": sys_id("incident", idx),
        "short_description": f"Incident {idx}",
        "number": f"INC000{idx}",
        "state": "1",
        "category": "software",
        "reopen_count": "0",
        "severity": "3",
        "assigned_to": {
            "link": f"https://dev-testing.service-now.com/api/now/table/sys_user/user-{idx}",
            "value": f"user-{idx}",
        },
        "urgency": "2",
        "contact_type": "email",
        "sys_created_on": created_on(idx),
        "sys_created_by": f"admin-{idx}",
        "active": "true",
        "priority": "3",
    }
