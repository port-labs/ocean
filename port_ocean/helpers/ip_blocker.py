"""
SSRF protection for SaaS runtime only: block outbound requests to private/loopback/link-local
and other non-public IP ranges. Resolve host from URL to IP(s), block if any fall in those ranges.
"""

import asyncio
import ipaddress
import socket

import httpx
from loguru import logger

from port_ocean.exceptions.clients import BlockedIPError

# Blocked outbound IP ranges (SSRF protection). Meaning of each:
#
# IPv4:
#   10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16  = private (your LAN, internal VPCs; never routable on the internet)
#   127.0.0.0/8                                 = loopback (localhost; "this machine")
#   169.254.0.0/16                              = link-local (same subnet only; includes cloud metadata 169.254.169.254)
#   0.0.0.0/8                                   = unspecified / "this" network (not a real destination)
#   255.255.255.255/32                          = broadcast (all hosts on local segment)
#   224.0.0.0/4                                 = multicast (group addresses, not a single host)
#   100.64.0.0/10                               = carrier-grade NAT (ISP internal, not public internet)
#   240.0.0.0/4                                 = reserved (IANA reserved, unused)
#
# IPv6:
#   ::1/128        = loopback (localhost)
#   fe80::/10      = link-local (same link only)
#   ::/128         = unspecified
#   fc00::/7       = unique local (like private IPv4, not routable on internet)
#   ff00::/8       = multicast
#   2001:db8::/32  = reserved for documentation (not real hosts)
#   100::/64       = discard prefix (RFC 6666; traffic dropped)

_BLOCKED_IPV4 = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "0.0.0.0/8",
    "255.255.255.255/32",
    "224.0.0.0/4",
    "100.64.0.0/10",
    "240.0.0.0/4",
]
_BLOCKED_IPV6 = [
    "::1/128",
    "fe80::/10",
    "::/128",
    "fc00::/7",
    "ff00::/8",
    "2001:db8::/32",
    "100::/64",
]
_NETS_V4 = frozenset(ipaddress.ip_network(c, strict=False) for c in _BLOCKED_IPV4)
_NETS_V6 = frozenset(ipaddress.ip_network(c, strict=False) for c in _BLOCKED_IPV6)

_TRUSTED_SUBDOMAINS = (
    # Port domains
    ".getport.io",
    ".port.io",
    # Third-party API domains
    ".aikido.dev",
    ".amplication.com",
    ".armorcode.com",
    ".atlassian.com",
    ".atlassian.net",
    ".azure.com",
    ".bitbucket.org",
    ".checkmarx.net",
    ".datadoghq.com",
    ".dynatrace.com",
    ".firehydrant.io",
    ".github.com",
    ".gitlab.com",
    ".komodor.com",
    ".launchdarkly.com",
    ".linear.app",
    ".management.azure.com",
    ".newrelic.com",
    ".octopus.com",
    ".okta.com",
    ".opsgenie.com",
    ".pagerduty.com",
    ".sentry.io",
    ".servicenow.com",
    ".service-now.com",
    ".snyk.io",
    ".sonarqube.org",
    ".statuspage.io",
    ".terraform.io",
    ".wiz.io",
)


async def _resolve_to_ip_addresses(hostname: str) -> list[str]:
    if not hostname:
        return []
    try:
        ipaddress.ip_address(hostname)
        return [hostname]
    except ValueError:
        pass

    addr_info = await asyncio.to_thread(
        socket.getaddrinfo,
        hostname,
        None,
        socket.AF_UNSPEC,
        socket.SOCK_STREAM,
    )
    return list[str](dict.fromkeys(str(info[4][0]) for info in addr_info if info[4]))


def _is_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    nets = _NETS_V4 if isinstance(ip, ipaddress.IPv4Address) else _NETS_V6
    return any(ip in n for n in nets)


class IPBlockerTransport(httpx.AsyncBaseTransport):
    """Blocks requests whose host resolves to a private/loopback/link-local/etc IP."""

    def __init__(self, wrapped: httpx.AsyncBaseTransport) -> None:
        self._wrapped = wrapped

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        hostname: str = request.url.host
        if any(hostname.endswith(subdomain) for subdomain in _TRUSTED_SUBDOMAINS):
            return await self._wrapped.handle_async_request(request)

        ip_addresses: list[str] = await _resolve_to_ip_addresses(hostname)
        if not ip_addresses:
            raise BlockedIPError(
                f"Request to {hostname} was blocked: Host could not resolve to any IP address"
            )
        blocked_ip_addresses: list[str] = [
            ip_address for ip_address in ip_addresses if _is_blocked(ip_address)
        ]
        if blocked_ip_addresses:
            raise BlockedIPError(
                f"Request to {hostname} was blocked: Host IP address {str(blocked_ip_addresses)} is not within the allowed ranges"
            )
        request.url = request.url.copy_with(host=ip_addresses[0])
        request.headers["Host"] = hostname
        request.extensions = {**request.extensions, "sni_hostname": hostname}
        logger.debug(
            f"Request to {hostname} was allowed: Host IP address {str(ip_addresses)} is within the allowed ranges"
        )
        return await self._wrapped.handle_async_request(request)

    async def aclose(self) -> None:
        await self._wrapped.aclose()
