from typing import Any

from loguru import logger


def retrieve_batch_size_config_value(
    settings: dict[str, Any], config_key: str, default_value: int
) -> int:
    logger.info(f"Retrieving optional config key '{config_key}'")
    try:
        return int(settings[config_key])
    except (ValueError, TypeError):
        logger.info(
            f"key '{config_key}' is not specified by user, using default value instead"
        )
        return default_value
