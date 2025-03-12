from typing import Any
from loguru import logger

FILE_PROPERTY_PREFIX = "file://"


def get_file_paths(entity_mapping: object) -> list[str]:
    """
    Extract file paths from an entity mapping object.

    Looks for strings that start with 'file://' in the mapping and its properties,
    and returns the paths without the prefix.

    Args:
        entity_mapping: The entity mapping object to scan.

    Returns:
        List of file paths found in mappings.
    """
    file_paths: list[str] = []

    mapping_dict: dict[str, Any] = vars(entity_mapping)

    for key, value in mapping_dict.items():
        if isinstance(value, str) and value.startswith(FILE_PROPERTY_PREFIX):
            path = value[len(FILE_PROPERTY_PREFIX) :]
            file_paths.append(path)
            logger.debug(f"Found file reference in '{key}': {value}")

    properties = mapping_dict.get("properties")
    if isinstance(properties, dict):
        for prop_key, prop_value in properties.items():
            if isinstance(prop_value, str) and prop_value.startswith(
                FILE_PROPERTY_PREFIX
            ):
                path = prop_value[len(FILE_PROPERTY_PREFIX) :]
                file_paths.append(path)
                logger.debug(
                    f"Found file reference in property '{prop_key}': {prop_value}"
                )

    return file_paths
