import pytest

from azure_devops.helpers.validate_config import validate_azure_devops_config

_EMPTY_SP = {
    "organization_urls": None,
    "client_id": None,
    "client_secret": None,
    "tenant_id": None,
}

_EMPTY_LEGACY = {
    "organization_url": None,
    "personal_access_token": None,
}


def test_legacy_single_org_config_passes() -> None:
    validate_azure_devops_config(
        organization_url="https://dev.azure.com/myorg",
        personal_access_token="pat-12345",
        **_EMPTY_SP,
    )


def test_legacy_config_missing_pat_raises() -> None:
    with pytest.raises(ValueError, match="requires either"):
        validate_azure_devops_config(
            organization_url="https://dev.azure.com/myorg",
            personal_access_token="",
            **_EMPTY_SP,
        )


def test_legacy_config_missing_url_raises() -> None:
    with pytest.raises(ValueError, match="requires either"):
        validate_azure_devops_config(
            organization_url="",
            personal_access_token="pat-12345",
            **_EMPTY_SP,
        )


def test_no_config_at_all_raises() -> None:
    with pytest.raises(ValueError, match="requires either"):
        validate_azure_devops_config(
            **_EMPTY_LEGACY,
            **_EMPTY_SP,
        )


def test_service_principal_config_passes() -> None:
    validate_azure_devops_config(
        **_EMPTY_LEGACY,
        organization_urls=[
            "https://dev.azure.com/org1",
            "https://dev.azure.com/org2",
        ],
        client_id="client-id",
        client_secret="client-secret",
        tenant_id="tenant-id",
    )


def test_service_principal_single_url_passes() -> None:
    validate_azure_devops_config(
        **_EMPTY_LEGACY,
        organization_urls=["https://dev.azure.com/only-org"],
        client_id="client-id",
        client_secret="client-secret",
        tenant_id="tenant-id",
    )


def test_service_principal_visualstudio_url_passes() -> None:
    validate_azure_devops_config(
        **_EMPTY_LEGACY,
        organization_urls=["https://myorg.visualstudio.com"],
        client_id="client-id",
        client_secret="client-secret",
        tenant_id="tenant-id",
    )


@pytest.mark.parametrize(
    "missing_field",
    ["client_id", "client_secret", "tenant_id"],
)
def test_service_principal_missing_credential_field_raises(missing_field: str) -> None:
    fields: dict[str, str | None] = {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "tenant_id": "tenant-id",
    }
    fields[missing_field] = None
    with pytest.raises(ValueError, match="requires either"):
        validate_azure_devops_config(
            **_EMPTY_LEGACY,
            organization_urls=["https://dev.azure.com/org1"],
            **fields,
        )


def test_service_principal_empty_urls_raises() -> None:
    with pytest.raises(ValueError, match="requires either"):
        validate_azure_devops_config(
            **_EMPTY_LEGACY,
            organization_urls=[],
            client_id="client-id",
            client_secret="client-secret",
            tenant_id="tenant-id",
        )


def test_mixing_legacy_and_sp_fields_raises() -> None:
    with pytest.raises(ValueError, match="mixes single-org fields"):
        validate_azure_devops_config(
            organization_url="https://dev.azure.com/legacy",
            personal_access_token="legacy-pat",
            organization_urls=["https://dev.azure.com/sp-org"],
            client_id="client-id",
            client_secret="client-secret",
            tenant_id="tenant-id",
        )


def test_mixing_legacy_with_partial_sp_fields_raises() -> None:
    with pytest.raises(ValueError, match="mixes single-org fields"):
        validate_azure_devops_config(
            organization_url="https://dev.azure.com/legacy",
            personal_access_token="legacy-pat",
            organization_urls=None,
            client_id="client-id",
            client_secret=None,
            tenant_id=None,
        )


def test_malformed_url_in_organization_urls_raises() -> None:
    with pytest.raises(ValueError, match="well-formed URL"):
        validate_azure_devops_config(
            **_EMPTY_LEGACY,
            organization_urls=["not-a-url"],
            client_id="client-id",
            client_secret="client-secret",
            tenant_id="tenant-id",
        )


def test_bare_path_in_organization_urls_raises() -> None:
    with pytest.raises(ValueError, match="well-formed URL"):
        validate_azure_devops_config(
            **_EMPTY_LEGACY,
            organization_urls=["/some/path"],
            client_id="client-id",
            client_secret="client-secret",
            tenant_id="tenant-id",
        )


def test_empty_string_in_organization_urls_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        validate_azure_devops_config(
            **_EMPTY_LEGACY,
            organization_urls=["https://dev.azure.com/valid", "   "],
            client_id="client-id",
            client_secret="client-secret",
            tenant_id="tenant-id",
        )
