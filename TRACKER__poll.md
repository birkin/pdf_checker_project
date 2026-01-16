# Polling implementation tracker

## Update log

### 2026-01-16 Session 2

- **What changed**
  - Created `scripts/process_verapdf_jobs.py` - cron script to process pending veraPDF jobs
  - Added `OpenRouterSummary` model to `pdf_checker_app/models.py`
  - Created migration `0003_add_openrouter_summary.py`
  - Added `summary_fragment` view to `views.py`
  - Added `summary.fragment` URL route to `config/urls.py`
  - Created `fragments/summary_fragment.html` template
  - Updated `report.html` to include summary section
  - Updated `view_report` to pass summary context
  - Created `tests/test_polling_endpoints.py` with 18 new tests

- **What works now**
  - HTMX polling for status, veraPDF, and summary fragments
  - Upload view marks documents as 'pending' and returns immediately
  - Cron script can process pending veraPDF jobs in background
  - All 22 tests pass

- **Not working / pending**
  - OpenRouter summary cron script (future implementation)
  - Actual OpenRouter API integration (future)

- **Decisions / assumptions**
  - Used `select_for_update(skip_locked=True)` in cron script to avoid double-processing
  - Summary fragment polls every 3s when pending/processing
  - Status fragment polls every 2s when pending/processing

- **Next steps**
  - Run migration: `uv run python manage.py migrate`
  - Set up cron job for `scripts/process_verapdf_jobs.py`
  - Implement OpenRouter summary cron script when ready

- **Commands run + outcomes**
  - `uv run python manage.py makemigrations pdf_checker_app --name add_openrouter_summary` → Created migration 0003
  - `uv run ./run_tests.py` → 22 tests pass
  - `uv run python manage.py migrate` → Applied migration 0003

### 2026-01-16 Session 2 (continued)

- **What changed**
  - Created `scripts/process_openrouter_summaries.py` - cron script for OpenRouter summary generation
    - Uses `httpx` for API calls (per AGENTS.md directive)
    - Finds docs with completed veraPDF but no summary
    - Calls OpenRouter API with veraPDF summary as context
    - Persists full response JSON + parsed fields to `OpenRouterSummary`
    - Supports `--dry-run` and `--batch-size` flags

- **What works now**
  - Full polling architecture is complete
  - Both cron scripts ready for deployment

- **Not working / pending**
  - Need to set `OPENROUTER_API_KEY` environment variable for summary script
  - Cron jobs need to be configured on server

- **Next steps**
  - Set up cron entries (e.g., every minute for veraPDF, every 5 minutes for summaries)
  - Test end-to-end with real PDF upload

- **Commands run + outcomes**
  - `uv run ./run_tests.py` → 22 tests pass

### YYYY-MM-DD HH:MM

- **What changed**
  - 
- **What works now**
  - 
- **Not working / pending**
  - 
- **Decisions / assumptions**
  - 
- **Next steps**
  - 
- **Commands run + outcomes**
  -

