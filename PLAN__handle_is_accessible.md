# Plan: Skip OpenRouter when veraPDF says accessible

Before making any coding changes, review `pdf_checker_project/AGENTS.md` for coding preferences.

## Goal
Avoid calling OpenRouter (sync and cron) when veraPDF reports the PDF is accessible. OpenRouter should only generate user-facing suggestions for non-accessible PDFs.

## Context snapshot (Jan 30, 2026)
- veraPDF compliance is parsed via `get_verapdf_compliant()` and `get_accessibility_assessment()` in `pdf_checker_app/lib/pdf_helpers.py`.
- Synchronous processing always attempts OpenRouter after successful veraPDF, regardless of accessibility result (`attempt_synchronous_processing()` calls `attempt_openrouter_sync()` unconditionally).
- Cron summary generation uses `scripts/process_openrouter_summaries.py` and selects any completed doc that has a veraPDF result and no OpenRouter summary; it does not check `is_accessible`.
- `VeraPDFResult.is_accessible` exists but is not populated by `save_verapdf_result()` yet (defaults to False). Plan should account for this.

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

## Refactor plan
1. **Persist accessibility on veraPDF save**
   - Update `save_verapdf_result()` to set `is_accessible` using `get_verapdf_compliant()`.
   - If compliance is `None`, decide on a default (likely `False`, or leave existing value). Document in code comments.

2. **Short-circuit OpenRouter in sync processing**
   - In `attempt_synchronous_processing()`, after `attempt_verapdf_sync()` succeeds, load the veraPDF result and skip `attempt_openrouter_sync()` when `is_accessible` is `True`.
   - Log a concise `info` message when skipping.

3. **Prevent cron from selecting accessible docs**
   - Update `find_pending_summaries()` to exclude documents with `verapdf_result__is_accessible=True`.
   - Ensure both “no summary” and “pending/failed summary” queries include this filter.

4. **Safety/edge handling**
   - If `VeraPDFResult.is_accessible` is missing or `None`, treat it as “needs suggestions” to preserve current behavior for unknown cases.
   - Confirm existing OpenRouter summaries remain displayable (no deletion required).

5. **Tests to add/adjust**
   - `test_sync_processing.py`
     - Add a test that `attempt_synchronous_processing()` skips OpenRouter when `is_accessible=True`.
     - Add a test that OpenRouter still runs when `is_accessible=False` (or `None`).
   - `test_polling_endpoints.py` (if summary fragment behavior depends on presence/absence of OpenRouter summary, consider no changes unless behavior needs updates).
   - Add tests for `find_pending_summaries()` to ensure accessible docs are excluded.

## Implementation notes
- Prefer single-return functions and avoid nested defs (per `AGENTS.md`).
- Maintain Python 3.12 typing conventions and PEP 604 unions.
- If OpenRouter depends on accessibility status during cron processing, ensure `save_verapdf_result()` is called before cron queues summaries.

## Expected behavior after change
- Accessible PDFs: veraPDF completes, document is marked completed, OpenRouter is not called, and no summary is queued by cron.
- Not-accessible PDFs: OpenRouter behaves as today (sync attempt, cron fallback).

## Suggested verification
- Run unit tests: `uv run ./run_tests.py`.
- Manual smoke: upload an accessible PDF and confirm suggestions are not generated.
