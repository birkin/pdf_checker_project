# Plan: Skip OpenRouter when veraPDF says accessible

Before making any coding changes, review `pdf_checker_project/AGENTS.md` for coding preferences.

## Goal
Avoid calling OpenRouter (sync and cron) when veraPDF reports the PDF is accessible. OpenRouter should only generate user-facing suggestions for non-accessible PDFs.

## Context snapshot (Jan 30, 2026)
- veraPDF compliance is parsed via `get_verapdf_compliant()` and `get_accessibility_assessment()` in `pdf_checker_app/lib/pdf_helpers.py`.
- Synchronous processing now skips OpenRouter when `VeraPDFResult.is_accessible` is true.
- Cron summary generation now excludes documents with `verapdf_result__is_accessible=True`.
- `save_verapdf_result()` now persists `is_accessible` based on veraPDF compliance (defaults to `False` when compliance is missing).

## Relevant code locations
- `pdf_checker_app/lib/pdf_helpers.py`:
  - `get_verapdf_compliant()`
  - `get_accessibility_assessment()`
  - `save_verapdf_result()`
- `pdf_checker_app/lib/sync_processing_helpers.py`:
  - `attempt_synchronous_processing()`
  - `attempt_verapdf_sync()`
  - `attempt_openrouter_sync()`
- `scripts/process_openrouter_summaries.py`:
  - `find_pending_summaries()`
  - `process_single_summary()`
- Tests:
  - `pdf_checker_app/tests/test_sync_processing.py`
  - `pdf_checker_app/tests/test_polling_endpoints.py`

## Assumptions
- The veraPDF compliance boolean is the single source of truth for accessibility.
- An accessible PDF should **not** have OpenRouter suggestions generated (sync or cron).

## Implementation summary
1. **Persist accessibility on veraPDF save**
   - `save_verapdf_result()` now sets `is_accessible` using `get_verapdf_compliant()` and defaults to `False` when compliance is missing.

2. **Short-circuit OpenRouter in sync processing**
   - `attempt_synchronous_processing()` loads `VeraPDFResult` and skips OpenRouter when `is_accessible` is `True`.
   - Logs an `info` message when skipping.

3. **Prevent cron from selecting accessible docs**
   - `find_pending_summaries()` excludes `verapdf_result__is_accessible=True` in both selection branches.

4. **Tests added/adjusted**
   - `test_sync_processing.py` covers the sync skip behavior and OpenRouter cron selection for accessible/non-accessible docs.
   - No changes required in `test_polling_endpoints.py`.

## Implementation notes
- Prefer single-return functions and avoid nested defs (per `AGENTS.md`).
- Maintain Python 3.12 typing conventions and PEP 604 unions.
- If OpenRouter depends on accessibility status during cron processing, ensure `save_verapdf_result()` is called before cron queues summaries.

## Expected behavior after change
- Accessible PDFs: veraPDF completes, document is marked completed, OpenRouter is not called, and no summary is queued by cron.
- Not-accessible PDFs: OpenRouter behaves as today (sync attempt, cron fallback).

## Verification
- Unit tests: `uv run ./run_tests.py` (confirmed passing).
- Manual smoke: upload an accessible PDF and confirm suggestions are not generated (pending).

---

# Plan: Hide suggestions section for accessible PDFs

## Goal
When veraPDF marks the PDF as accessible, the report page should not render the “Accessibility Improvement Suggestions” section or its placeholder text.

## Context snapshot (Jan 31, 2026)
- The summary fragment now receives `assessment` so accessible PDFs can skip the suggestions section.
- `summary_fragment.html` renders nothing when `assessment == 'accessible'`.
- A summary fragment test asserts the suggestions section is hidden for accessible PDFs.

## Relevant code locations
- `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/report.html`
- `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/fragments/summary_fragment.html`
- `pdf_checker_app/views.py` (`view_report()` and `summary_fragment()`)

## Implementation summary
1. **Expose accessibility state to templates**
   - `summary_fragment()` now passes `assessment` in the fragment context.

2. **Update template conditional**
   - `summary_fragment.html` guards the suggestions section when `assessment == 'accessible'`.

3. **Tests added/adjusted**
   - `test_polling_endpoints.py` includes a case ensuring accessible PDFs do not render the suggestions section.

## Implementation notes
- Reuse existing `assessment` values: `accessible` vs `not-accessible`.
- Keep the summary fragment behavior unchanged for non-accessible PDFs.

## Verification
- Unit tests: `GITHUB_ACTIONS=true uv run ./run_tests.py` (confirmed passing).
- Manual: load report for an accessible PDF and confirm the “Accessibility Improvement Suggestions” section is absent (confirmed).
