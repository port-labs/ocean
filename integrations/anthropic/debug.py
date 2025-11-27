"""Debug script for Anthropic integration development and testing."""

from port_ocean.core.utils import init_ocean

# Initialize the Ocean framework for debugging
init_ocean(
    application_class_path='main:AnthropicIntegration',
    config_file_path='config.yaml'
)