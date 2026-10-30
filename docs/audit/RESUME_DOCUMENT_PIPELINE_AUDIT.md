# Resume and Document Pipeline Audit

## Actual pipeline

```text
upload bytes
 -> MasterResumeParser magic/extension extraction
 -> entities
 -> DocumentDB + PROPOSED FactDB rows
 -> user confirm/reject
 -> active verified FactDB rows
 -> Eligibility/Scoring
 -> ResumeService deterministic or Gemini/fallback StructuredResume
 -> FactualConsistencyValidator
 -> ResumeDB JSON + ResumeClaimDB
 -> render PDF/DOCX on request
 -> HTTP Response / frontend Blob download
```

Evidence: `candidates.py:412-544`, `applications.py:438-543`, `applications.py:685-801`, `web/src/api/client.ts:57-105`.

## Findings

| ID | Severity/status | Evidence and observed behavior | Required correction |
|---|---|---|---|
| RES-001 | P1 / BR contributor | `resume_parser.py:319-333,412-420` defaults missing graduation year to 2024, field to Computer Science, institution to Accredited University, and fallback experience to Tech Corp/Python/FastAPI. These are claims not extracted from evidence. | Return unknown/proposed fields, never invented institution/company/skill values; block generation until user confirms or omit the field. |
| RES-002 | P1 / PF | `ResumeDB` stores structured JSON and a PDF SHA-256 (`models.py:149-159`), but PDF/DOCX bytes are regenerated in `applications.py:709-770`; there is no durable artifact path/blob or renderer-version binding. | Persist durable artifacts or content-addressed storage metadata, renderer version, and exact bytes/hash; ensure download returns the approved artifact. |
| RES-003 | P1 / PF | Upload writes `storage/documents/<candidate_id>/<hash>_<filename>` (`candidates.py:437-442`) with no byte-size limit; frontend accepts only `.pdf,.txt` (`ResumeImportWorkflow.tsx:123-128`) despite backend DOCX support. | Enforce server-side size/type/signature limits, accept DOCX in UI, handle encrypted/unreadable files, and use a durable configured storage root. |
| RES-004 | P1 / PF | Re-upload updates facts by `key`, resets them to PROPOSED (`candidates.py:474-487`), but there is no active master-document pointer/version selection; status selects latest document only (`candidates.py:380-408`). | Add explicit master version table/pointer, supersede facts with provenance, and support safe replacement/deletion/restore. |
| RES-005 | P2 / IU | Parser cleans control characters, rejects insufficient searchable PDF text, extracts PDF/DOCX/TXT, and links proposed facts to `source_document_id`; `tests/integration/test_master_resume_upload.py` passes. | Add scanned-PDF OCR policy or explicit unsupported state, not just a generic parse error. |
| RES-006 | P1 / PF | `normalize_resume_content` deduplicates bullets by first 80 characters and the current uncommitted pipeline regression test passes, but `ResumeClaimDB` is created only for section bullets; entry bullets and edited metadata are not independently validated. | Validate every rendered claim/entry against active fact IDs and compare rendered bytes to the approved content hash. |
| RES-007 | P2 / IU | Current targeted/full tests verify `%PDF-`, A4 dimensions, one page for the supplied reference, extractable text, MIME, `Content-Disposition`, and expected filename. | Add multi-page overflow, Unicode/bullet, missing contact, font fallback, and browser Blob tests. |
| RES-008 | P1 / PF | `generate_cover_letter_endpoint` and `update_cover_letter` mutate the current ResumeDB JSON (`applications.py:847-864,910-928`) without creating a new document/version or invalidating approval hashes. | Store cover-letter versions separately or include a new immutable package version and revoke approvals. |
| RES-009 | P2 / PF | `_get_cover_letter_context` uses `candidate@jov.si` and `+14155552671` fallbacks (`applications.py:948-952`) when fields are missing. | Omit missing contacts or require user input; never place placeholder contact data in exported documents. |
| RES-010 | P2 / IU | Filename helper sanitizes candidate names and current tests verify `Firstname_Lastname_CV.ext` (`resume.py:39-57`, `test_resume_pipeline_e2e.py:355-366`). | Keep filename source tied to the authenticated candidate, not client fallback text; add Unicode/quote header tests. |

## Reference artifacts

The supplied reference PDF exists at `storage/documents/68dd9203-93c2-4635-a0d9-6428d53432f7/f3610a92f8b3ab71_Prosun_Banerjee_CV.pdf`. The named broken DOCX was not found by repository-wide DOCX search. The reference test is present and passed in the current suite. No conclusion about the absent broken DOCX can be made.

## Download conclusion

The current endpoint path is materially different from the earlier failed `pdf.txt — Failed — No file` behavior: the uncommitted frontend uses `fetch`, checks `response.ok`, reads `Blob`, parses `Content-Disposition`, and clicks a Blob URL (`web/src/api/client.ts:57-105`). Current tests verify binary PDF responses. The remaining risk is that the bytes are regenerated on demand and can differ from the hash stored at generation time.
