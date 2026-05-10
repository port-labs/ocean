from urllib.parse import urlparse

_MODE_HINT = (
    "Azure DevOps integration requires either:\n"
    "  (a) organizationUrl + personalAccessToken for single-org mode, or\n"
    "  (b) organizationUrls + clientId + clientSecret + tenantId for "
    "Service Principal multi-org mode."
)


def validate_azure_devops_config(
    organization_url: str | None,
    personal_access_token: str | None,
    organization_urls: list[str] | None,
    client_id: str | None,
    client_secret: str | None,
    tenant_id: str | None,
) -> None:
    """Validate Azure DevOps integration config at startup.

    Exactly one of the two modes must be configured:
    - single-org PAT, or
    - Service Principal multi-org.
    """
    is_single_org = bool(organization_url) and bool(personal_access_token)
    has_any_sp_field = bool(
        client_id or client_secret or tenant_id or organization_urls
    )
    has_all_sp_fields = bool(
        organization_urls and client_id and client_secret and tenant_id
    )

    if not is_single_org and not has_all_sp_fields:
        raise ValueError(_MODE_HINT)

    if is_single_org and has_any_sp_field:
        raise ValueError(
            "Azure DevOps integration config mixes single-org fields with "
            f"Service Principal fields.\n{_MODE_HINT}"
        )

    if has_all_sp_fields:
        _validate_organization_urls(organization_urls or [])


def _validate_organization_urls(organization_urls: list[str]) -> None:
    if not organization_urls:
        raise ValueError("organizationUrls must contain at least one organization URL.")

    for raw_url in organization_urls:
        if not isinstance(raw_url, str) or not raw_url.strip():
            raise ValueError(
                "organizationUrls entries must be non-empty organization URL strings."
            )
        parsed = urlparse(raw_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(
                f"organizationUrls entry '{raw_url}' is not a well-formed URL "
                f"(expected e.g. 'https://dev.azure.com/{{organization}}')."
            )
