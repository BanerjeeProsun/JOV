"""Architectural Lint: Prohibit brittle locators and coordinate clicks.

Rules from Blueprint v2.0 Section 10:
- Role, label, placeholder and test-id locators only.
- No xpath=
- No mouse.click(
- No coordinates
"""

from pathlib import Path
import re
import pytest


FORBIDDEN_PATTERNS = [
    (re.compile(r"xpath=", re.IGNORECASE), "XPath locators are forbidden"),
    (re.compile(r"mouse\.click\(", re.IGNORECASE), "Coordinate clicks (mouse.click) are forbidden"),
    (re.compile(r"\.click\(\s*position=", re.IGNORECASE), "Position coordinates are forbidden"),
]


def test_no_forbidden_locators_in_adapters() -> None:
    """Scan all adapter code for forbidden locator patterns."""
    adapters_dir = Path("src/jovsi/adapters")
    if not adapters_dir.exists():
        return

    violations = []
    for py_file in adapters_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pattern, desc in FORBIDDEN_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append(f"{py_file.relative_to(Path('.'))}: {desc} ('{match.group(0)}')")

    assert not violations, f"Forbidden locator patterns found: {violations}"
