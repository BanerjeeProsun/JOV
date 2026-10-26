"""Unit tests for SSRFSafeFetcher and URL validation."""

import socket
from unittest.mock import MagicMock, patch
import pytest

from jovsi.adapters.ssrf import (
    SSRFSafeFetcher,
    SSRFValidationError,
    is_ip_allowed,
    validate_url,
)


def test_is_ip_allowed():
    # Restricted IPs
    assert is_ip_allowed("127.0.0.1") is False
    assert is_ip_allowed("127.0.0.2") is False
    assert is_ip_allowed("10.0.0.1") is False
    assert is_ip_allowed("10.254.1.2") is False
    assert is_ip_allowed("172.16.0.1") is False
    assert is_ip_allowed("172.31.255.255") is False
    assert is_ip_allowed("192.168.1.1") is False
    assert is_ip_allowed("169.254.169.254") is False
    assert is_ip_allowed("0.0.0.0") is False
    assert is_ip_allowed("100.64.0.1") is False
    assert is_ip_allowed("192.0.2.1") is False
    assert is_ip_allowed("198.51.100.1") is False
    assert is_ip_allowed("203.0.113.1") is False
    assert is_ip_allowed("224.0.0.1") is False
    assert is_ip_allowed("240.0.0.1") is False
    assert is_ip_allowed("255.255.255.255") is False

    # IPv6 restricted
    assert is_ip_allowed("::1") is False
    assert is_ip_allowed("fe80::1") is False
    assert is_ip_allowed("fc00::1") is False
    assert is_ip_allowed("ff02::1") is False

    # Public safe IPs
    assert is_ip_allowed("8.8.8.8") is True
    assert is_ip_allowed("1.1.1.1") is True
    assert is_ip_allowed("104.26.10.78") is True
    assert is_ip_allowed("2606:4700::6810:a4e") is True


def test_validate_url_schemes():
    # Disallow non-http/https
    for scheme_url in [
        "file:///etc/passwd",
        "file:///C:/Windows/win.ini",
        "ftp://ftp.example.com",
        "gopher://example.com",
        "data:text/plain;base64,SGVsbG8=",
        "javascript:alert(1)",
    ]:
        with pytest.raises(SSRFValidationError, match="Scheme .* not allowed"):
            validate_url(scheme_url)


def test_validate_url_credentials():
    with pytest.raises(SSRFValidationError, match="Credentials in URLs are forbidden"):
        validate_url("https://admin:secret@example.com/job")


def test_validate_url_restricted_literals():
    for target in [
        "http://127.0.0.1:8000/api",
        "http://localhost:8000/test",
        "http://10.0.1.5/admin",
        "http://172.20.0.1/status",
        "http://192.168.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[::1]:8000/",
        "http://[fe80::1]/",
    ]:
        with pytest.raises(SSRFValidationError):
            validate_url(target)


def test_validate_url_dns_resolution_failure():
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
        with pytest.raises(SSRFValidationError, match="Could not resolve hostname"):
            validate_url("https://nonexistent-company-domain-4040.org/job")


def test_validate_url_dns_resolving_to_private_ip():
    # Hostname resolves to loopback / internal private IP
    fake_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    with patch("socket.getaddrinfo", return_value=fake_addr_info):
        with pytest.raises(SSRFValidationError, match="resolved to restricted address"):
            validate_url("https://evil-spoofed-domain.com/jobs/1")

    # Hostname resolves to AWS/GCP metadata
    fake_meta_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]
    with patch("socket.getaddrinfo", return_value=fake_meta_info):
        with pytest.raises(SSRFValidationError, match="resolved to restricted address"):
            validate_url("http://cloud-meta.internal.org/")


def test_validate_url_valid_public_domain():
    fake_public_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=fake_public_info):
        url, host, port = validate_url("https://example.com/careers/lead-engineer")
        assert url == "https://example.com/careers/lead-engineer"
        assert host == "example.com"
        assert port == 443


def test_ssrf_safe_fetch_caps_response_size():
    # Simulate a stream that yields more bytes than max_bytes
    fake_public_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=fake_public_info):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.iter_bytes.return_value = [b"A" * 500, b"B" * 600]

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.stream.return_value.__enter__.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            with pytest.raises(SSRFValidationError, match="exceeded maximum permitted limit"):
                SSRFSafeFetcher.fetch("https://example.com/huge-file", max_bytes=800)


def test_ssrf_safe_fetch_blocks_malicious_redirect():
    # Hop 1 is public, but redirects to 169.254.169.254
    fake_public_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=fake_public_info):
        mock_resp1 = MagicMock()
        mock_resp1.status_code = 302
        mock_resp1.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.stream.return_value.__enter__.return_value = mock_resp1

        with patch("httpx.Client", return_value=mock_client):
            with pytest.raises(SSRFValidationError, match="Access to restricted IP '169.254.169.254' is forbidden"):
                SSRFSafeFetcher.fetch("https://example.com/redirect-to-metadata")
