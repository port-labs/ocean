"""
Debug module for Zendesk integration

Following Ocean integration patterns for debug configuration.

Purpose: Enable debug mode for the integration during development
Expected output: Debug-enabled integration instance
"""

if __name__ == "__main__":
    # Enable debug mode for local development
    # This allows running the integration locally for testing
    
    from port_ocean.core.ocean import Ocean
    from integration import ZendeskIntegration

    # Create and run the integration in debug mode
    integration = ZendeskIntegration()
    ocean = Ocean(integration=integration, app_path="./main.py")
    ocean.run()