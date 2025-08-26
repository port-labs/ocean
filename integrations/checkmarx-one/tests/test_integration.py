import pytest
from unittest.mock import MagicMock, patch

from integration import (
    CheckmarxOneIntegration,
    CheckmarxOneApplicationResourcesConfig,
    CheckmarxOneProjectResourcesConfig,
    CheckmarxOneScanResourcesConfig,
    CheckmarxOneScanResultResourcesConfig,
    CheckmarxOneApplicationSelector,
    CheckmarxOneProjectSelector,
    CheckmarxOneScanSelector,
    CheckmarxOneResultSelector,
)


class TestCheckmarxOneSelectors:
    """Tests for Checkmarx One selectors."""

    def test_application_selector_defaults(self):
        """Test application selector default values."""
        selector = CheckmarxOneApplicationSelector()
        assert selector.criticality is None

    def test_project_selector_defaults(self):
        """Test project selector default values.""" 
        selector = CheckmarxOneProjectSelector()
        assert selector.application_ids == []
        assert selector.groups is None

    def test_scan_selector_defaults(self):
        """Test scan selector default values."""
        selector = CheckmarxOneScanSelector()
        assert selector.project_ids == []
        assert selector.scanner_types is None
        assert selector.scan_status is None

    def test_scan_result_selector_defaults(self):
        """Test scan result selector default values."""
        selector = CheckmarxOneResultSelector()
        assert selector.severity is None
        assert selector.state is None
        assert selector.status is None
        assert selector.exclude_result_types == ["DEV_AND_TEST"]
        assert selector.scanner_types is None

    def test_application_selector_with_values(self):
        """Test application selector with custom values."""
        selector = CheckmarxOneApplicationSelector(criticality=[2, 3])
        assert selector.criticality == [2, 3]

    def test_project_selector_with_values(self):
        """Test project selector with custom values."""
        selector = CheckmarxOneProjectSelector(
            application_ids=["app-1", "app-2"],
            groups=["group-1", "group-2"]
        )
        assert selector.application_ids == ["app-1", "app-2"]
        assert selector.groups == ["group-1", "group-2"]

    def test_scan_selector_with_values(self):
        """Test scan selector with custom values."""
        selector = CheckmarxOneScanSelector(
            project_ids=["proj-1", "proj-2"],
            scanner_types=["sast", "sca"],
            scan_status=["Completed"]
        )
        assert selector.project_ids == ["proj-1", "proj-2"]
        assert selector.scanner_types == ["sast", "sca"] 
        assert selector.scan_status == ["Completed"]

    def test_scan_result_selector_with_values(self):
        """Test scan result selector with custom values."""
        selector = CheckmarxOneResultSelector(
            severity=["CRITICAL", "HIGH"],
            state=["TO_VERIFY"],
            status=["NEW"],
            exclude_result_types=["NONE"],
            scanner_types=["sast"]
        )
        assert selector.severity == ["CRITICAL", "HIGH"]
        assert selector.state == ["TO_VERIFY"]
        assert selector.status == ["NEW"]
        assert selector.exclude_result_types == ["NONE"]
        assert selector.scanner_types == ["sast"]


class TestCheckmarxOneResourceConfigs:
    """Tests for Checkmarx One resource configurations."""

    def test_application_resource_config(self):
        """Test application resource configuration."""
        selector = CheckmarxOneApplicationSelector(criticality=[3])
        config = CheckmarxOneApplicationResourcesConfig(
            kind="application",
            selector=selector
        )
        assert config.kind == "application"
        assert config.selector.criticality == [3]

    def test_project_resource_config(self):
        """Test project resource configuration."""
        selector = CheckmarxOneProjectSelector(application_ids=["app-1"])
        config = CheckmarxOneProjectResourcesConfig(
            kind="project",
            selector=selector
        )
        assert config.kind == "project"
        assert config.selector.application_ids == ["app-1"]

    def test_scan_resource_config(self):
        """Test scan resource configuration."""
        selector = CheckmarxOneScanSelector(project_ids=["proj-1"])
        config = CheckmarxOneScanResourcesConfig(
            kind="scan",
            selector=selector
        )
        assert config.kind == "scan"
        assert config.selector.project_ids == ["proj-1"]

    def test_scan_result_resource_config(self):
        """Test scan result resource configuration."""
        selector = CheckmarxOneResultSelector(severity=["HIGH"])
        config = CheckmarxOneScanResultResourcesConfig(
            kind="scan_result",
            selector=selector
        )
        assert config.kind == "scan_result"
        assert config.selector.severity == ["HIGH"]


class TestCheckmarxOneIntegration:
    """Tests for Checkmarx One integration."""

    def test_integration_app_config_class(self):
        """Test integration app config class is properly configured."""
        integration = CheckmarxOneIntegration()
        assert hasattr(integration, "AppConfigHandlerClass")
        
        # Test that the config class is set correctly
        app_config_class = integration.AppConfigHandlerClass
        assert hasattr(app_config_class, "CONFIG_CLASS")

    def test_integration_initialization(self):
        """Test integration can be initialized."""
        integration = CheckmarxOneIntegration()
        assert integration is not None
        assert isinstance(integration, CheckmarxOneIntegration)