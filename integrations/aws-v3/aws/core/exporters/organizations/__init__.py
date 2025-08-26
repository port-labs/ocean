"""AWS Organizations exporters package."""

from aws.core.exporters.organizations.account.exporter import (
    OrganizationsAccountExporter,
)

__all__ = ["OrganizationsAccountExporter"]
