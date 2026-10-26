"""SSRF-Safe HTTP Fetcher and URL Validator.

Enforces strict SSRF defense across all outbound HTTP requests:
1. Only http and https protocols permitted.
2. Credentials in URLs forbidden.
3. DNS resolution with strict validation against loopback, private, link-local,
   and cloud metadata IP ranges (IPv4 & IPv6).
4. Re-validation of destination target IP on every redirect hop.
5. Response size capping and timeout enforcement.
"""

import ipaddress
import socket
import urllib.parse
from typing import List, Optional, Set, Tuple
import httpx


class SSRFValidationError(ValueError):
    """Raised when an outbound URL fails SSRF safety validation."""
    pass


# Restricted IPv4 networks
RESTRICTED_IPV4_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),        # Private RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),     # Private RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),    # Private RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / Cloud metadata (AWS, GCP, Azure)
    ipaddress.ip_network("0.0.0.0/8"),         # Current network
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved for future use
    ipaddress.ip_network("255.255.255.255/32"),# Limited broadcast
]

# Restricted IPv6 networks
RESTRICTED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),           # Loopback
    ipaddress.ip_network("::/128"),            # Unspecified
    ipaddress.ip_network("fe80::/10"),         # Link-local
    ipaddress.ip_network("fc00::/7"),          # Unique local (ULA)
    ipaddress.ip_network("ff00::/8"),          # Multicast
    ipaddress.ip_network("64:ff9b::/96"),      # IPv4/IPv6 translation
    ipaddress.ip_network("2001:db8::/32"),     # Documentation
]

BLOCKED_HOSTNAMES: Set[str] = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.internal",
    "metadata",
    "instance-data",
}


def is_ip_allowed(ip_str: str) -> bool:
    """Return True if IP is public and safe; False if private/loopback/restricted."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    # Standard python is_private, is_loopback, is_link_local, is_multicast, is_reserved checks
    if (
        ip_obj.is_loopback
        or ip_obj.is_private
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        return False

    if isinstance(ip_obj, ipaddress.IPv4Address):
        for net in RESTRICTED_IPV4_NETWORKS:
            if ip_obj in net:
                return False
    elif isinstance(ip_obj, ipaddress.IPv6Address):
        for net in RESTRICTED_IPV6_NETWORKS:
            if ip_obj in net:
                return False

    return True


def validate_url(url: str) -> Tuple[str, str, int]:
    """Validate URL protocol, credentials, hostname, and resolved IP addresses.

    Returns:
        (canonical_url, hostname, port)
    Raises:
        SSRFValidationError on any violation.
    """
    if not url or not isinstance(url, str):
        raise SSRFValidationError("URL must be a non-empty string.")

    cleaned_url = url.strip()
    try:
        parsed = urllib.parse.urlsplit(cleaned_url)
    except Exception as exc:
        raise SSRFValidationError(f"Invalid URL structure: {exc}")

    # 1. Permitted schemes
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFValidationError(f"Scheme '{parsed.scheme}' not allowed. Only http and https are permitted.")

    # 2. No credentials in URL
    if parsed.username or parsed.password:
        raise SSRFValidationError("Credentials in URLs are forbidden.")

    # 3. Hostname checks
    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL must contain a valid hostname.")

    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES or hostname_lower.endswith(".internal"):
        raise SSRFValidationError(f"Access to hostname '{hostname}' is restricted by SSRF policy.")

    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)

    # 4. Check if hostname is direct IP literal
    is_ip = False
    try:
        ip_obj = ipaddress.ip_address(hostname)
        is_ip = True
    except ValueError:
        pass

    if is_ip:
        if not is_ip_allowed(str(ip_obj)):
            raise SSRFValidationError(f"Access to restricted IP '{hostname}' is forbidden.")
        return cleaned_url, hostname, port

    # 5. Resolve DNS and validate every resolved IP
    try:
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFValidationError(f"Could not resolve hostname '{hostname}': {exc}")

    if not addr_info:
        raise SSRFValidationError(f"No address information resolved for '{hostname}'.")

    resolved_ips = {item[4][0] for item in addr_info}
    for resolved_ip in resolved_ips:
        if not is_ip_allowed(resolved_ip):
            raise SSRFValidationError(
                f"Hostname '{hostname}' resolved to restricted address '{resolved_ip}'."
            )

    return cleaned_url, hostname, port


class SSRFSafeFetcher:
    """Safe HTTP Client with DNS validation, redirect checks, and response size capping."""

    DEFAULT_TIMEOUT = 8.0
    DEFAULT_MAX_BYTES = 1_048_576  # 1 MB
    DEFAULT_MAX_REDIRECTS = 3
    DEFAULT_USER_AGENT = "JOV.si/1.0 (+https://jov.si; contact@jov.si)"

    @classmethod
    def fetch(
        cls,
        url: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        headers: Optional[dict] = None,
    ) -> httpx.Response:
        """Fetch URL with SSRF protection, redirect re-validation, and response size cap."""
        req_headers = {
            "User-Agent": cls.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        }
        if headers:
            req_headers.update(headers)

        current_url = url
        redirect_count = 0

        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            while True:
                # 1. Validate destination URL and resolved IPs before connecting
                canonical_url, _, _ = validate_url(current_url)

                # 2. Make request with streaming to cap body size
                try:
                    with client.stream("GET", canonical_url, headers=req_headers) as response:
                        # 3. Check for redirect responses (301, 302, 303, 307, 308)
                        if response.status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get("Location")
                            if not location:
                                raise SSRFValidationError(f"Redirect status {response.status_code} missing Location header.")

                            redirect_count += 1
                            if redirect_count > max_redirects:
                                raise SSRFValidationError(f"Exceeded maximum redirects ({max_redirects}).")

                            # Resolve relative redirects
                            next_url = urllib.parse.urljoin(current_url, location)
                            current_url = next_url
                            continue

                        # 4. Stream response content up to max_bytes
                        chunks: List[bytes] = []
                        total_bytes = 0
                        for chunk in response.iter_bytes():
                            total_bytes += len(chunk)
                            if total_bytes > max_bytes:
                                raise SSRFValidationError(
                                    f"Response size exceeded maximum permitted limit of {max_bytes} bytes."
                                )
                            chunks.append(chunk)

                        content = b"".join(chunks)

                        # Reconstruct standard httpx.Response object for caller
                        full_response = httpx.Response(
                            status_code=response.status_code,
                            headers=response.headers,
                            content=content,
                            request=response.request,
                        )
                        return full_response

                except httpx.RequestError as exc:
                    raise SSRFValidationError(f"HTTP request failed: {exc}")
