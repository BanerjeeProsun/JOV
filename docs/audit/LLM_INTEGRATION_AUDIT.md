# JOV.si LLM Integration Audit

## Configuration

| Item | Observed value/path |
|---|---|
| Provider abstraction | `src/jovsi/services/llm.py:59-95` |
| Supported concrete provider | Google Gemini REST (`GeminiLLMProvider`) |
| Selected provider | `gemini` from `JOVSI_LLM_PROVIDER`/default (`config.py:45-49`) |
| Selected model | `gemini-2.5-flash` from `JOVSI_LLM_MODEL`/default |
| API-key variable names | `JOVSI_LLM_API_KEY`, `JOVSI_GEMINI_API_KEY` equivalent field, and documented `GEMINI_API_KEY` mismatch in `.env.example:27-34` |
| Loading | `src/jovsi/config.py:28-57` via Pydantic Settings, `JOVSI_` prefix; extra env names are ignored unless separately mapped |
| HTTP endpoint | `https://generativelanguage.googleapis.com/v1beta` (`llm.py:106`) |
| Consumers | `ResumeService.generate_tailored_resume` (`resume.py:387-470`) and `generate_tailored_cover_letter` (`resume.py:1079-1153`) |
| Fallback | deterministic `FallbackLLMProvider`; hybrid service routes to fallback on provider error |
| Health endpoint | `GET /api/v1/health/llm` (`api/main.py:162-165`) |

## Verification result

The live health command returned provider `gemini`, model `gemini-2.5-flash`, `configured=false`, `status=unconfigured`. No provider call was made because no key is configured. Unit tests mock Gemini HTTP and verify header placement/JSON parsing (`tests/unit/test_llm_provider.py:88-155`); those are contract tests, not an integration success.

## Findings

- **LLM-001 BC/P1:** no configured credentials, so tailored operations use deterministic fallback. The UI/Settings surface does not prove that a configured provider exists.
- **LLM-002 PF/P1:** provider configuration naming is inconsistent: Pydantic uses `GEMINI_API_KEY` as a field under `JOVSI_` prefix while `.env.example` documents unprefixed `GEMINI_API_KEY`; `settings.effective_llm_api_key` does not guarantee the documented unprefixed variable is loaded.
- **LLM-003 PF/P1:** generation is gated by `if settings.GEMINI_API_KEY` (`resume.py:402` and `1094`), not the hybrid service's `LLM_ENABLED`/effective key contract. A configured `JOVSI_LLM_API_KEY` can be ignored by the tailoring branch.
- **LLM-004 PF/P2:** token count/cost accounting is not persisted; `LLMResult.token_count` is returned in memory only.
- **LLM-005 PF/P1:** prompts identify facts as verified and job text as content, but there is no explicit untrusted-data delimiter/instruction for prompt injection resistance. LLM output is validated for resume/letter facts, but it is not used as a security or final eligibility authority.
- **LLM-006 PF/P1:** exception handling logs only a truncated generic warning but returns deterministic content without a user-visible “fallback used” status in the review workflow beyond generator metadata.

## Secret exposure review

No secret value was printed. The Gemini client sends the key in `x-goog-api-key` (`llm.py:137-143`), masks `repr`, and health responses expose only configured/status metadata. The reset-token path is a separate secret-exposure defect covered by `SEC-002`.

## Required repairs/tests

Unify env names, honor `LLM_ENABLED` and the effective key consistently, show provider source/model in the review UI, persist bounded usage/cost telemetry, add prompt-delimiter/injection fixtures, validate structured output after every provider call, and add one opt-in live smoke test that requires an explicitly supplied credential without logging it.
