from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SailPointAuthConfig(BaseModel):
    tenant: str = Field(..., description="Your SailPoint tenant subdomain")
    client_id: str
    client_secret: str
    pat_token: Optional[str] = None
    scope: Optional[str] = None


class SailPointFilterConfig(BaseModel):
    identities_status: Optional[str] = Field(None, description="e.g., ACTIVE, INACTIVE")
    identities_updated_since_days: Optional[int] = None
    accounts_source_id: Optional[str] = None
    entitlements_name_contains: Optional[str] = None
    entitlements_name_startswith: Optional[str] = None

    raw: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-kind raw query param map, e.g., {'identities': {'limit': 250}}",
    )


class SailPointRuntimeConfig(BaseModel):
    page_size: int = 200
    max_concurrency: int = 5
    max_retries: int = 5
    base_backoff_ms: int = 200
    webhook_hmac_secret: Optional[str] = None


class SailPointConfig(BaseModel):
    auth: SailPointAuthConfig
    filters: SailPointFilterConfig = SailPointFilterConfig()
    runtime: SailPointRuntimeConfig = SailPointRuntimeConfig()

    generic_resources: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="key = resource name (e.g., 'lifecycleEvents'), value = {path, blueprint, mapping}",
    )
