from typing import Any

from azure_devops.client.auth import ACCOUNT_MODE_MULTIPLE, ACCOUNT_MODE_SINGLE


def validate_azure_devops_config(config: dict[str, Any]) -> None:
    """Validate the integration config based on account_mode.

    Raises ValueError for any invalid or incomplete configuration.
    """
    account_mode = config.get("account_mode", ACCOUNT_MODE_SINGLE)

    if account_mode == ACCOUNT_MODE_SINGLE:
        if not config.get("organization_url"):
            raise ValueError(
                "Single Account mode requires 'organizationUrl'."
            )
        if not config.get("personal_access_token"):
            raise ValueError(
                "Single Account mode requires 'personalAccessToken'."
            )

    elif account_mode == ACCOUNT_MODE_MULTIPLE:
        for field in ("client_id", "client_secret", "tenant_id"):
            if not config.get(field):
                raise ValueError(
                    f"Multiple Accounts mode requires '{field}'."
                )
        raw_urls = config.get("organization_urls", "")
        org_urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
        if not org_urls:
            raise ValueError(
                "Multiple Accounts mode requires at least one URL in 'organizationUrls'."
            )
        for url in org_urls:
            if not url.startswith("http"):
                raise ValueError(
                    f"Invalid organization URL '{url}' in 'organizationUrls'."
                )

    else:
        raise ValueError(
            f"Unknown account_mode '{account_mode}'. "
            f"Expected '{ACCOUNT_MODE_SINGLE}' or '{ACCOUNT_MODE_MULTIPLE}'."
        )
