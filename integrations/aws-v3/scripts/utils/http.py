"""HTTP download helpers."""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request

from scripts.utils.ssl import SslConfig


def download_text(url: str, *, ssl_config: SslConfig | None = None, timeout: int = 60) -> str:
    config = ssl_config or SslConfig()
    request = urllib.request.Request(url)
    context = config.create_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Failed to download from {url}: {error}") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, ssl.SSLCertVerificationError):
            raise RuntimeError(
                f"Failed to download from {url}: SSL certificate verification failed. "
                "If you are behind a corporate proxy, set SSL_CA_BUNDLE to your CA bundle path "
                "or disable verification with SslConfig(verify=False)."
            ) from error
        raise RuntimeError(f"Failed to download from {url}: {error}") from error
