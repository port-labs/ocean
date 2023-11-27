from typing import Any

from loguru import logger


def retrieve_batch_size_config_value(
    settings: dict[str, Any], config_key: str, default_value: int
) -> int:
    logger.info(f"Retrieving optional config key '{config_key}'")
    try:
        return int(settings[config_key])
    except ValueError:
        logger.info(
            f"key '{config_key}' is not specified by user, using default value instead"
        )
        return default_value


def produce_job_url_from_build_url(build_url: str) -> str:
    splitted_build = build_url.split("/")
    if build_url[-1] == "/":  # means the url ends with a slash
        return "/".join(splitted_build[:-2]) + "/"
    return "/".join(splitted_build[:-1]) + "/"
