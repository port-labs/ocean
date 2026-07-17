import pytest

from azure_devops.helpers.validate_config import (
    parse_organization_urls,
    validate_azure_devops_config,
)


class TestParseOrganizationUrls:
    def test_none_returns_empty(self) -> None:
        assert parse_organization_urls(None) == []

    def test_empty_string_returns_empty(self) -> None:
        assert parse_organization_urls("") == []

    def test_empty_list_returns_empty(self) -> None:
        assert parse_organization_urls([]) == []

    def test_list_input_strips_and_normalizes(self) -> None:
        result = parse_organization_urls(
            ["https://dev.azure.com/org1/", "  https://dev.azure.com/org2  "]
        )
        assert result == [
            "https://dev.azure.com/org1",
            "https://dev.azure.com/org2",
        ]

    def test_comma_separated_string_splits(self) -> None:
        result = parse_organization_urls(
            "https://dev.azure.com/org1,https://dev.azure.com/org2"
        )
        assert result == [
            "https://dev.azure.com/org1",
            "https://dev.azure.com/org2",
        ]

    def test_list_skips_blank_entries(self) -> None:
        result = parse_organization_urls(["https://dev.azure.com/org1", "", "  "])
        assert result == ["https://dev.azure.com/org1"]

    def test_trailing_slash_stripped(self) -> None:
        assert parse_organization_urls(["https://dev.azure.com/org/"]) == [
            "https://dev.azure.com/org"
        ]


class TestValidateAzureDevopsConfig:
    def test_single_mode_valid(self) -> None:
        validate_azure_devops_config(
            {
                "account_mode": "Single Account",
                "organization_url": "https://dev.azure.com/org",
                "personal_access_token": "secret",
            }
        )

    def test_single_mode_missing_url_raises(self) -> None:
        with pytest.raises(ValueError, match="organizationUrl"):
            validate_azure_devops_config(
                {
                    "account_mode": "Single Account",
                    "personal_access_token": "secret",
                }
            )

    def test_single_mode_missing_pat_raises(self) -> None:
        with pytest.raises(ValueError, match="personalAccessToken"):
            validate_azure_devops_config(
                {
                    "account_mode": "Single Account",
                    "organization_url": "https://dev.azure.com/org",
                }
            )

    def test_multiple_mode_valid(self) -> None:
        validate_azure_devops_config(
            {
                "account_mode": "Multiple Accounts",
                "client_id": "cid",
                "client_secret": "csecret",
                "tenant_id": "tid",
                "organization_urls": ["https://dev.azure.com/org1"],
            }
        )

    def test_multiple_mode_missing_client_id_raises(self) -> None:
        with pytest.raises(ValueError, match="client_id"):
            validate_azure_devops_config(
                {
                    "account_mode": "Multiple Accounts",
                    "client_secret": "csecret",
                    "tenant_id": "tid",
                    "organization_urls": ["https://dev.azure.com/org1"],
                }
            )

    def test_multiple_mode_empty_urls_raises(self) -> None:
        with pytest.raises(ValueError, match="organizationUrls"):
            validate_azure_devops_config(
                {
                    "account_mode": "Multiple Accounts",
                    "client_id": "cid",
                    "client_secret": "csecret",
                    "tenant_id": "tid",
                    "organization_urls": [],
                }
            )

    def test_multiple_mode_invalid_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid organization URL"):
            validate_azure_devops_config(
                {
                    "account_mode": "Multiple Accounts",
                    "client_id": "cid",
                    "client_secret": "csecret",
                    "tenant_id": "tid",
                    "organization_urls": ["not-a-url"],
                }
            )

    def test_unknown_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown account_mode"):
            validate_azure_devops_config({"account_mode": "Hybrid"})
