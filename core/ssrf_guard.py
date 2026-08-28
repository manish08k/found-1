"""SSRF guard for outbound HTTP requests issued by workflow nodes (http.request)."""
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

ALLOWED_SCHEMES = {"http", "https"}

_BLOCKED_PORTS = {25, 587, 465, 2375, 2376, 6379, 5432, 27017, 9200, 11211}

_METADATA_IPS = {
    "169.254.169.254",   # AWS / GCP / Azure / Oracle instance metadata
    "100.100.100.200",   # Alibaba Cloud metadata
    "fd00:ec2::254",     # AWS IMDSv2 IPv6
}


def _is_blocked_ip(ip_str: str) -> bool:
    if ip_str in _METADATA_IPS:
        return True
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Blocked URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("URL has no hostname")
    if parsed.port and parsed.port in _BLOCKED_PORTS:
        raise ValueError(f"Blocked destination port: {parsed.port}")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {parsed.hostname}") from exc

    if not infos:
        raise ValueError(f"Could not resolve host: {parsed.hostname}")

    for _family, _type, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        if _is_blocked_ip(ip_str):
            raise ValueError(
                f"Blocked destination IP {ip_str} (resolved from {parsed.hostname})"
            )


class SSRFSafeTransport(httpx.AsyncHTTPTransport):
    """Re-validates the destination on every hop, including redirects."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        assert_safe_url(str(request.url))
        return await super().handle_async_request(request)
