"""Tests for Okta integration."""

import pytest
from unittest.mock import Mock, patch

from integration import (
    OktaUserConfig,
    OktaGroupConfig,
    OktaUserSelector,
    OktaGroupSelector,
    OktaPortAppConfig,
    OktaIntegration,
)


class TestOktaIntegration:
    """Test cases for Okta integration configuration."""

    def test_okta_user_selector(self):
        """Test OktaUserSelector configuration."""
        selector = OktaUserSelector(
            include_groups=True,
            include_applications=True,
        )
        assert selector.include_groups is True
        assert selector.include_applications is True

    def test_okta_user_config(self):
        """Test OktaUserConfig configuration."""
        selector = OktaUserSelector()
        config = OktaUserConfig(
            selector=selector,
            kind="okta-user",
        )
        assert config.kind == "okta-user"
        assert isinstance(config.selector, OktaUserSelector)

    def test_okta_group_selector(self):
        """Test OktaGroupSelector configuration."""
        selector = OktaGroupSelector(
            include_members=True,
        )
        assert selector.include_members is True

    def test_okta_group_config(self):
        """Test OktaGroupConfig configuration."""
        selector = OktaGroupSelector()
        config = OktaGroupConfig(
            selector=selector,
            kind="okta-group",
        )
        assert config.kind == "okta-group"
        assert isinstance(config.selector, OktaGroupSelector)

 

    def test_okta_port_app_config(self):
        """Test OktaPortAppConfig configuration."""
        user_config = OktaUserConfig(
            selector=OktaUserSelector(),
            kind="okta-user",
        )
        group_config = OktaGroupConfig(
            selector=OktaGroupSelector(),
            kind="okta-group",
        )
        port_config = OktaPortAppConfig(
            resources=[user_config, group_config],
        )

        assert len(port_config.resources) == 2
        assert any(resource.kind == "okta-user" for resource in port_config.resources)
        assert any(resource.kind == "okta-group" for resource in port_config.resources)
 

