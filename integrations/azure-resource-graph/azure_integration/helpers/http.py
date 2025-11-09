import textwrap
from urllib.parse import urlparse, parse_qs

DEFAULT_HTTP_REQUEST_TIMEOUT = 60


def format_query(query: str) -> str:
    # remove outer single/double quotes
    query = query.strip().strip("'").strip('"')
    # dedent and normalize
    query = textwrap.dedent(query).strip()
    return query


def parse_url_components(url: str) -> tuple[str, dict[str, str]]:
    """Extract query params from a full URL (handles %24skiptoken decoding)."""
    parsed = urlparse(url)
    endpoint = parsed.path.rstrip("/")
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    return endpoint, params
