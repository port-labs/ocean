import pytest
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    MappingsConfig,
    EntityMapping,
)


def test_port_resource_config_embed_original_data_default():
    """Test that embed_original_data defaults to None for backward compatibility"""
    config = PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier="test",
                blueprint="test",
            )
        ),
        items_to_parse=".items",
    )
    assert config.embed_original_data is None


def test_port_resource_config_embed_original_data_explicit_true():
    """Test that embed_original_data can be set to True"""
    config = PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier="test", 
                blueprint="test",
            )
        ),
        items_to_parse=".items",
        embed_original_data=True,
    )
    assert config.embed_original_data is True


def test_port_resource_config_embed_original_data_explicit_false():
    """Test that embed_original_data can be set to False"""
    config = PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier="test",
                blueprint="test", 
            )
        ),
        items_to_parse=".items",
        embed_original_data=False,
    )
    assert config.embed_original_data is False


def test_port_resource_config_embed_original_data_alias():
    """Test that embedOriginalData alias works"""
    config_dict = {
        "entity": {
            "mappings": {
                "identifier": "test",
                "blueprint": "test",
            }
        },
        "itemsToParse": ".items",
        "embedOriginalData": False,
    }
    config = PortResourceConfig.parse_obj(config_dict)
    assert config.embed_original_data is False