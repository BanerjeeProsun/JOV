"""Portal Detector: URL matching and policy lookup (Blueprint v2.0 Section 10).

No browser involvement.
"""

from urllib.parse import urlparse
from pydantic import BaseModel
from typing import Optional


class PortalMatch(BaseModel):
    portal_key: str
    is_supported: bool
    requires_auth: bool = False
    automation_allowed: bool = False
    host: str


class PortalDetector:
    @classmethod
    def detect(cls, url: str) -> PortalMatch:
        """Analyze URL and determine portal match and policy."""
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()

        if host in ("127.0.0.1:8765", "localhost:8765"):
            return PortalMatch(
                portal_key="mock_portal",
                is_supported=True,
                requires_auth=False,
                automation_allowed=True,
                host=host,
            )

        # For external portals in Release 1
        return PortalMatch(
            portal_key="external_unsupported",
            is_supported=False,
            requires_auth=True,
            automation_allowed=False,
            host=host,
        )
