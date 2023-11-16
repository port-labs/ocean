from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from loguru import logger


def sanitize_url(url):
    # Parse the URL
    parsed_url = urlparse(url)

    # Remove leading and trailing whitespaces from components
    sanitized_scheme = parsed_url.scheme.strip()
    sanitized_netloc = parsed_url.netloc.strip()
    sanitized_path = parsed_url.path.strip()
    sanitized_params = parsed_url.params.strip()
    sanitized_query = parsed_url.query.strip()
    sanitized_fragment = parsed_url.fragment.strip()

    # Reconstruct the sanitized URL
    sanitized_url = urlunparse((
        sanitized_scheme,
        sanitized_netloc,
        sanitized_path,
        sanitized_params,
        sanitized_query,
        sanitized_fragment
    ))

    return sanitized_url


def convert_timestamp_to_utc_dt(timestamp) -> [str, None]:
    try:
        # Convert timestamp to datetime object
        dt_object = datetime.fromtimestamp(timestamp / 1000.0, tz=timezone.utc)

        # Format datetime object as a string
        formatted_string = dt_object.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
        return formatted_string
    except Exception as e:
        logger.exception(e)
