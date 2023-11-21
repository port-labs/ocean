from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse, quote
from loguru import logger


def sanitize_url(input_url):
    try:
        components = urlparse(input_url)
        sanitized_components = [comp.strip() for comp in components]
        sanitized_url = urlunparse(sanitized_components)
        return sanitized_url
    except Exception as e:
        logger.exception(f"Error sanitizing URL: {e}")
        return input_url


def convert_timestamp_to_utc(timestamp) -> [str, None]:
    try:
        dt_object = datetime.fromtimestamp(timestamp / 1000.0, tz=timezone.utc)
        formatted_string = dt_object.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        return formatted_string
    except Exception as e:
        logger.exception(f"Error converting timestamp: {e}")
        return None


def url_encode(input_string) -> str:
    try:
        encoded_string = quote(input_string)
        return encoded_string
    except Exception as e:
        logger.exception(f"Error encoding string: {e}")
        return ""