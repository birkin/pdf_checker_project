# Plan: Retire OPENROUTER_MODEL

Before making any code-changes, review `pdf_checker_project/AGENTS.md` for coding preferences.

## Summary

Retire the legacy `OPENROUTER_MODEL` environment variable and rely solely on `OPENROUTER_MODEL_ORDER` for model selection. Remove fallback logic and update messaging/docs so missing config errors are clear and consistent.

## Opinion on current logic

Your intent is solid. The current implementation already prefers `OPENROUTER_MODEL_ORDER` and only falls back to `OPENROUTER_MODEL` when the order is empty, which creates an implicit two-path configuration and increases ambiguity. Removing the fallback will make behavior deterministic and avoid drifting configuration across environments.

## Functions/files that will need updates

### OpenRouter helpers
- `pdf_checker_app/lib/openrouter_helpers.py`
  - `get_model()` (remove the function and its uses).
  - `get_model_order()` (remove fallback to `get_model()`, return only the parsed order).

### Synchronous processing
- `pdf_checker_app/lib/sync_processing_helpers.py`
  - `attempt_openrouter_sync()` (error path: currently treats missing model order as missing credentials; keep but ensure error message references only `OPENROUTER_MODEL_ORDER` if applicable).

### Cron processing script
- `scripts/process_openrouter_summaries.py`
  - Module docstring (remove requirement for `OPENROUTER_MODEL`).
  - `process_summaries()` error log message currently references `OPENROUTER_MODEL_ORDER or OPENROUTER_MODEL`.
  - `get_model_order()` wrapper remains but should rely on updated helper.

### Tests/docs (if present)
- Any tests or docs that mention `OPENROUTER_MODEL` should be updated or removed.

## Implementation plan

1. **Remove `OPENROUTER_MODEL` references in helpers** — ✅ done
   - Deleted `get_model()` in `openrouter_helpers.py`.
   - Simplified `get_model_order()` to parse only `OPENROUTER_MODEL_ORDER` and return an empty list if unset.

2. **Update callers and error messages** — ⚠️ partial
   - Updated the cron script error message to reference only `OPENROUTER_MODEL_ORDER`.
   - `attempt_openrouter_sync()` log messaging still treats missing model order as missing credentials (no OPENROUTER_MODEL reference, but consider adjusting wording if desired).

3. **Update documentation strings and runtime guidance** — ✅ done (script header)
   - Updated `scripts/process_openrouter_summaries.py` header to mention only `OPENROUTER_MODEL_ORDER`.
   - No other docs found mentioning `OPENROUTER_MODEL` (aside from this plan).

4. **Testing (minimal)** — ⚠️ partial
   - Updated `pdf_checker_app/tests/test_sync_processing.py` to stop patching `get_model()` and instead patch `get_model_order()`.
     - Updated tests:
       - `SyncOpenRouterProcessingTest.test_openrouter_sync_success`
       - `SyncOpenRouterProcessingTest.test_openrouter_sync_timeout_fallback`
       - `SyncOpenRouterProcessingTest.test_openrouter_sync_error_marks_failed`
       - `SyncOpenRouterProcessingTest.test_openrouter_skipped_without_credentials`
       - `FullSyncProcessingTest.test_full_sync_success_path`
   - Rerun `uv run ./run_tests.py` to confirm green.
   - Consider adding a focused unit test for `get_model_order()` behavior (empty string -> `[]`).

## Context for a future work session

- The fallback behavior lives solely in `openrouter_helpers.get_model_order()`; removing it is the core behavioral change.
- The only places that read model order are:
  - `sync_processing_helpers.attempt_openrouter_sync()`
  - `scripts/process_openrouter_summaries.process_summaries()`
- Logs currently reference `OPENROUTER_MODEL` in the cron script; keep consistency after removal.
- Any environment documentation or deployment configs (e.g., `.env`, infra scripts) may still define `OPENROUTER_MODEL`; those should be cleaned up at the same time if present.
