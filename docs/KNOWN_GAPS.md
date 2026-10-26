# JOV.si — Known Gaps, Limitations, and Unresolved Dependencies

**Document Version:** 2.0.0  
**Last Updated:** 2026-10-26  

This document honestly catalogs all intentional architectural boundaries, external dependencies awaiting credentials, unsupported portals, and known limitations in Release 1.

---

## 1. Release 1 Safety Boundaries

### 1.1 Mock-Only Submission Sandbox
- **Status:** Active & Enforced by Design.
- **Description:** In Release 1, all automated browser submissions are strictly restricted to the local mock portal (`http://127.0.0.1:8765`).
- **Limitation:** The submitter adapter explicitly refuses any host not in `JOVSI_SUBMIT_HOST_ALLOWLIST`. Real employer portals (e.g., Workday, Greenhouse, Lever, Taleo) cannot be submitted to automatically in Release 1.
- **Path to Resolution:** Milestone 6+ introduces per-portal policy reviews, manual assist mode (`MANUAL_HANDOFF`), and supervised submission mode behind two independent configuration switches.

### 1.2 Email Verification (E3 via Mailbox)
- **Status:** Deferred / Not Implemented in Release 1.
- **Description:** Verification level E3 via direct IMAP/POP3 mailbox scanning for confirmation emails is omitted in Release 1 to prevent requiring user email account credentials.
- **Current Mitigation:** E3 verification is supported via independent portal status / "my applications" lookup pages (`/status?ref=&email=`).
- **Path to Resolution:** A future plugin can implement an OAuth2-scoped email inbox reader.

---

## 2. External Services & Credentials

### 2.1 LLM Provider Availability
- **Status:** Optional / Fallback Default Active.
- **Description:** An external LLM API (e.g., Gemini or OpenAI) can be configured via environment variables (`JOVSI_LLM_API_KEY`). When unset or `JOVSI_LLM_ENABLED=false`, JOV.si operates 100% deterministically using the algorithmic lexical matcher, template engine, and pure rule extractors.
- **Limitation:** Without an active LLM key, bullet wording improvements are disabled and the deterministic fact-assembly pipeline is used.

### 2.2 Commercial Job Board APIs
- **Status:** Unconfigured / Documentation Cataloged.
- **Description:** Real job discovery currently supports user URL import, manual job text import, and public structured feeds. Third-party private APIs (LinkedIn, Indeed, ZipRecruiter) require commercial partner agreements and API keys not present in the local environment.

---

## 3. Platform & Browser Automation Constraints

## 2.3 Onboarding cinematic media
- **Status:** Implemented as an in-product Motion/SVG fallback.
- **Description:** This workspace does not provide a verified video-generation or local video-rendering pipeline. The onboarding experience therefore uses the original, local `AmbientBackdrop` SVG animation rather than claiming a generated video asset exists.
- **Behavior:** The ambient composition is silent, lightweight, and disabled by the user's reduced-motion preference. It does not delay page rendering or run behind operational workspace screens.

### 3.1 CAPTCHA & Cloudflare Bot Management
- **Status:** Handled via `MANUAL_HANDOFF`.
- **Description:** JOV.si contains zero bot evasion, CAPTCHA solving, or browser fingerprint spoofing code, in strict accordance with Invariant 10.
- **Behavior:** Encountering an unexpected CAPTCHA transitions the application to `MANUAL_HANDOFF`, alerting the user to complete the step.

### 3.2 Dynamic Complex SPAs (Shadow DOM / Canvas)
- **Status:** Restricted to Standard Accessible Web Elements.
- **Description:** Portal forms using non-standard canvas rendering or inaccessible shadow DOMs cannot be reliably mapped using role, label, or test-id locators.
- **Mitigation:** The adapter raises `AdapterError`, triggering `MANUAL_HANDOFF` with a structured copy sheet of candidate answers.
