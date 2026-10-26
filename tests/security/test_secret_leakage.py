"""Security tests for secret leakage in git tracked files, commits, and logs."""

import re
import subprocess
from pathlib import Path


SECRET_PATTERNS = [
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("OpenAI API Key", re.compile(r"sk-[a-zA-Z0-9]{32,}")),
    ("OpenAI Project Key", re.compile(r"sk-proj-[a-zA-Z0-9_\-]{40,}")),
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private Key", re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PGP)? ?PRIVATE KEY-----")),
    ("GitHub Token", re.compile(r"gh[pousr]_[0-9a-zA-Z]{36}")),
    ("Generic Bearer Secret", re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{40,}")),
]

# Patterns or test placeholders that are intentionally allowed in tests
EXEMPT_FILES = {
    "tests/security/test_secret_leakage.py",
}


def test_no_secrets_in_tracked_files():
    """Verify that no real API secrets or private keys are in git-tracked files."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    tracked_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

    findings = []
    for rel_path in tracked_files:
        if rel_path in EXEMPT_FILES:
            continue
        path = Path(rel_path)
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for name, pattern in SECRET_PATTERNS:
            matches = pattern.findall(content)
            for match in matches:
                # Disallow real keys
                if "your-gemini-api-key-here" not in match and "dummy" not in match.lower():
                    findings.append(f"{name} found in {rel_path}: {match[:8]}...")

    assert not findings, f"Secrets detected in tracked files: {findings}"


def test_env_file_is_git_ignored():
    """Verify that .env and variations are ignored by git."""
    for filename in [".env", ".env.local", ".env.production", ".env.staging"]:
        proc = subprocess.run(
            ["git", "check-ignore", filename],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        assert proc.returncode == 0, f"{filename} is not ignored by git!"


def test_no_secrets_in_recent_git_history():
    """Verify that recent commits do not contain leaked secrets in diffs."""
    proc = subprocess.run(
        ["git", "log", "-p", "-n", "30"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    diff_text = proc.stdout or ""

    findings = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            for name, pattern in SECRET_PATTERNS:
                matches = pattern.findall(line)
                for match in matches:
                    if "your-gemini-api-key-here" not in match and "dummy" not in match.lower():
                        findings.append(f"{name} in diff: {match[:8]}...")

    assert not findings, f"Secrets found in git history diffs: {findings}"
