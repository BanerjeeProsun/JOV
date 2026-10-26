"""Untrusted Input Sanitizer for hostile web pages and job postings (Blueprint v2.0 Section 13)."""

import hashlib
import re
import unicodedata
from typing import Tuple


# Regex patterns for stripping tags and hidden content
SCRIPT_TAG_RE = re.compile(r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", re.IGNORECASE)
STYLE_TAG_RE = re.compile(r"<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>", re.IGNORECASE)
IFRAME_TAG_RE = re.compile(r"<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>", re.IGNORECASE)
HTML_COMMENTS_RE = re.compile(r"<!--[\s\S]*?-->")

# Hidden elements: aria-hidden="true" or inline style with display:none / visibility:hidden
HIDDEN_ELEMENT_RE = re.compile(
    r"<[^>]+(?:aria-hidden\s*=\s*['\"]true['\"]|style\s*=\s*['\"][^'\"]*(?:display\s*:\s*none|visibility\s*:\s*hidden)[^'\"]*)[^>]*>[\s\S]*?<\/[^>]+>",
    re.IGNORECASE,
)
HTML_TAGS_RE = re.compile(r"<[^>]+>")

# Zero-width and bidirectional control characters
# U+200B (zero-width space), U+200C (zero-width non-joiner), U+200D (zero-width joiner)
# U+FEFF (zero-width no-break space / BOM), U+200E / U+200F (LTR / RTL marks)
# U+202A to U+202E (directional embeddings/overrides), U+2066 to U+2069 (directional isolates)
ZERO_WIDTH_AND_BIDI_RE = re.compile(
    r"[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E\u2060-\u2069]"
)

DEFAULT_MAX_LENGTH = 30000


class UntrustedInputSanitizer:
    @classmethod
    def sanitize(cls, raw_input: str, max_length: int = DEFAULT_MAX_LENGTH) -> Tuple[str, str]:
        """Sanitize hostile input, returning (raw_sha256, cleaned_text)."""
        if not raw_input:
            return hashlib.sha256(b"").hexdigest(), ""

        # 1. Compute raw sha256
        raw_bytes = raw_input.encode("utf-8")
        raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # 2. Strip scripts, styles, iframes, and HTML comments
        text_stage = SCRIPT_TAG_RE.sub(" ", raw_input)
        text_stage = STYLE_TAG_RE.sub(" ", text_stage)
        text_stage = IFRAME_TAG_RE.sub(" ", text_stage)
        text_stage = HTML_COMMENTS_RE.sub(" ", text_stage)

        # 3. Drop elements hidden by CSS or aria-hidden
        text_stage = HIDDEN_ELEMENT_RE.sub(" ", text_stage)

        # 4. Strip any remaining HTML tags to extract text only
        text_stage = HTML_TAGS_RE.sub(" ", text_stage)

        # 5. Unicode NFKC normalisation
        text_stage = unicodedata.normalize("NFKC", text_stage)

        # 6. Remove zero-width and bidirectional control characters
        text_stage = ZERO_WIDTH_AND_BIDI_RE.sub("", text_stage)

        # 7. Collapse whitespace
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text_stage.splitlines()]
        cleaned_text = "\n".join(line for line in lines if line)

        # 8. Cap length
        if len(cleaned_text) > max_length:
            cleaned_text = cleaned_text[:max_length]

        return raw_sha256, cleaned_text
