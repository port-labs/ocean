from typing import Any

from mocks.payloads import (
    SERVICENOW_PASSWORD,
    SERVICENOW_URL,
    SERVICENOW_USERNAME,
)

# jq transform used by the default mapping to normalise ServiceNow timestamps.
_CREATED_ON = (
    '.sys_created_on | (strptime("%Y-%m-%d %H:%M:%S") | strftime("%Y-%m-%dT%H:%M:%SZ"))'
)

# Shared selector for every kind — mirrors .port/resources/port-app-config.yaml.
_SELECTOR: dict[str, Any] = {
    "query": "true",
    "apiQueryParams": {
        "sysparmDisplayValue": "true",
        "sysparmExcludeReferenceLink": "false",
    },
}


def integration_config() -> dict[str, Any]:
    """Config overrides for the harness — uses Basic auth (no auth HTTP call)."""
    return {
        "integration": {
            "identifier": "test-servicenow",
            "type": "servicenow",
            "config": {
                "servicenow_url": SERVICENOW_URL,
                "servicenow_username": SERVICENOW_USERNAME,
                "servicenow_password": SERVICENOW_PASSWORD,
                "enable_tables_live_events_webhooks": False,
            },
        }
    }


def _resource(kind: str, blueprint: str, mappings: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "selector": _SELECTOR,
        "port": {"entity": {"mappings": {"blueprint": f'"{blueprint}"', **mappings}}},
    }


def mapping_for_kind(kind: str) -> dict[str, Any]:
    resources: dict[str, dict[str, Any]] = {
        "sys_user_group": _resource(
            "sys_user_group",
            "servicenowGroup",
            {
                "identifier": ".sys_id",
                "title": ".name",
                "properties": {
                    "description": ".description",
                    "isActive": ".active",
                    "createdOn": _CREATED_ON,
                    "createdBy": ".sys_created_by",
                },
            },
        ),
        "sc_catalog": _resource(
            "sc_catalog",
            "servicenowCatalog",
            {
                "identifier": ".sys_id",
                "title": ".title",
                "properties": {
                    "description": ".description",
                    "isActive": ".active",
                    "createdOn": _CREATED_ON,
                    "createdBy": ".sys_created_by",
                },
            },
        ),
        "incident": _resource(
            "incident",
            "servicenowIncident",
            {
                "identifier": ".sys_id",
                "title": ".short_description",
                "properties": {
                    "number": ".number | tostring",
                    "state": ".state",
                    "category": ".category",
                    "reopenCount": ".reopen_count",
                    "severity": ".severity",
                    "assignedTo": ".assigned_to.link",
                    "urgency": ".urgency",
                    "contactType": ".contact_type",
                    "createdOn": _CREATED_ON,
                    "createdBy": ".sys_created_by",
                    "isActive": ".active",
                    "priority": ".priority",
                },
            },
        ),
    }

    if kind not in resources:
        raise ValueError(f"No mapping defined for kind: {kind}")

    return {"resources": [resources[kind]]}
