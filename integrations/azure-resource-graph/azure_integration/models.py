from typing import Optional
from azure.identity.aio import ClientSecretCredential
from pydantic import BaseModel


class ResourceGroupTagFilters(BaseModel):
    included: Optional[dict[str, str]] = None
    excluded: Optional[dict[str, str]] = None

    def has_filters(self) -> bool:
        """Check if any filters are configured."""
        return bool(self.included) or bool(self.excluded)


class AuthCredentials(BaseModel):
    client_id: str
    client_secret: str
    tenant_id: str

    def create_azure_credential(self) -> ClientSecretCredential:
        return ClientSecretCredential(
            client_id=self.client_id,
            client_secret=self.client_secret,
            tenant_id=self.tenant_id,
        )


class ResourceExporterOptions(BaseModel):
    tag_filter: Optional[ResourceGroupTagFilters] = None
    resource_types: Optional[list[str]] = None


class ResourceContainerExporterOptions(BaseModel):
    tag_filter: Optional[ResourceGroupTagFilters] = None
