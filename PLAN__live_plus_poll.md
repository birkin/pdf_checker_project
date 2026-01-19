# PLAN__run_synchronously_with_timeouts.md

## Objective

On a “Check Accessibility” click, attempt to complete the work *synchronously* (veraPDF + OpenRouter) when it is fast enough, but automatically fall back to the existing HTMX polling + cron-driven processing when a call hits a timeout.

Target behavior:

- Try veraPDF with a hard timeout of **30 seconds**.
- If veraPDF succeeds, try OpenRouter with a hard timeout of **30 seconds**.
- If either timeout is hit, do **not** fail the request; redirect to the report page as usual and let polling + cron finish the work.
- Preserve the current polling UX (status fragment every ~2s; summary fragment every ~3s) and cron scripts as the “steady-state” backstop.

## Current architecture snapshot (baseline)

- `views.upload_pdf()` currently **does not** run veraPDF; it writes a `PDFDocument` row with `processing_status='pending'` and redirects immediately to the report page.
- The report page polls `status_fragment.html` every ~2s until the `PDFDocument.processing_status` is terminal (`completed`/`failed`), and then triggers a one-time load of the veraPDF fragment.
- Background veraPDF work is performed via `scripts/process_verapdf_jobs.py` which selects documents in `pending` or `processing` and runs veraPDF.
- Background OpenRouter work is performed via `scripts/process_openrouter_summaries.py` which selects documents with `processing_status='completed'` and either missing or `pending` `OpenRouterSummary` rows; it uses `httpx` with an OpenRouter timeout (currently 60 seconds).

## Design constraints (from AGENTS.md)

Implementation should follow the repository directives (Python 3.12 typing, httpx, no nested functions, simple `main()`, etc.).

## Proposed change set

### A. Add explicit “sync attempt” timeouts as first-class settings

Add two settings (constants) in `config/settings.py`:

- `VERAPDF_SYNC_TIMEOUT_SECONDS: float = 30.0`
- `OPENROUTER_SYNC_TIMEOUT_SECONDS: float = 30.0`

Optionally keep the cron script OpenRouter timeout separate (e.g., 60 seconds) so background jobs can be slightly more patient than the web request.

### B. Make veraPDF invocation support timeouts cleanly

Update `pdf_checker_app/lib/pdf_helpers.py`:

1. Change the signature of `run_verapdf()` to accept an optional timeout:

   - `def run_verapdf(pdf_path: Path, verapdf_path: Path, timeout_seconds: float | None = None) -> dict:`

2. Pass `timeout=timeout_seconds` into `subprocess.run(...)`.

3. Add a small, explicit exception type:

   - `class VeraPDFTimeoutError(Exception): ...`

4. Translate `subprocess.TimeoutExpired` into `VeraPDFTimeoutError` so views and cron code can branch cleanly.

This allows:
- web request path to treat *timeouts* as “defer to background”
- cron path to treat *timeouts* as “failed” (or retryable), depending on desired policy

### C. Avoid double-processing between “sync attempt” and cron (important)

Right now, `scripts/process_verapdf_jobs.py` selects `processing_status__in=['pending','processing']`. If a sync attempt marks a document `processing`, the cron runner may grab and re-run it concurrently (especially if cron runs every minute).

Introduce a timestamp field on `PDFDocument`:

- `processing_started_at = models.DateTimeField(blank=True, null=True)`

Then adjust selection rules:

1. Web request path sets:
   - `processing_status='processing'`
   - `processing_started_at=now()`
2. Cron job selection changes from “pending or processing” to:

   - Always include `pending`
   - Include `processing` **only if** `processing_started_at` is older than a threshold (e.g., 10 minutes), to support crash recovery

Example policy:

- `RECOVER_STUCK_PROCESSING_AFTER_SECONDS = 600`

This prevents the cron runner from competing with an in-flight sync attempt while still retaining the “recover stuck processing jobs” behavior.

### D. Share OpenRouter logic between cron and web request path

Currently, `scripts/process_openrouter_summaries.py` contains prompt construction, “failure check filtering”, and OpenRouter API call/parse logic.

To avoid duplicating that logic in `views.upload_pdf()`, extract it into a reusable module:

- `pdf_checker_app/lib/openrouter_helpers.py` (or `openrouter_client.py`)

Move (or re-home) these pieces:

- `PROMPT` template
- prompt-building function(s) (including any JSON reduction logic)
- `call_openrouter(...)` using `httpx`
- `parse_openrouter_response(...)`
- `persist_openrouter_summary(...)` (or “apply parsed response to model instance”)

Then:
- cron script imports and uses these helpers
- upload view uses the same helper for the sync attempt

Keep the cron script focused on:
- selecting eligible documents
- orchestrating calls
- logging + CLI flags (`--dry-run`, `--batch-size`, `-v`)

### E. Implement synchronous “best effort” in `views.upload_pdf()`

Update the upload flow to:

1. Upload and persist the file as currently done (checksum-based).
2. Create `PDFDocument` in DB (as currently done).
3. Attempt synchronous veraPDF:

   - set `processing_status='processing'`, `processing_started_at=now()`
   - call `run_verapdf(..., timeout_seconds=VERAPDF_SYNC_TIMEOUT_SECONDS)`
   - on success: parse + `save_verapdf_result(...)`
   - then set `processing_status='completed'` (veraPDF complete)
   - on `VeraPDFTimeoutError`: set `processing_status='pending'` (or keep `processing`, but pending is clearer) and redirect to report to allow polling + cron
   - on other exceptions: set `processing_status='failed'` and set `processing_error`

4. If veraPDF succeeded, attempt synchronous OpenRouter:

   - Create or update `OpenRouterSummary` row **before** calling OpenRouter, with:
     - `status='processing'`
     - `requested_at=now()`
   - Call OpenRouter with `timeout_seconds=OPENROUTER_SYNC_TIMEOUT_SECONDS`
   - On success:
     - persist parsed response fields
     - set `status='completed'`, `completed_at=now()`, `error=None`
   - On timeout:
     - set `status='pending'` (so cron can pick it up)
     - leave a minimal marker in `error` (optional) like: “Sync attempt timed out; will retry in background.”
   - On non-timeout exception:
     - set `status='failed'` + `error=str(exc)` (current behavior)

Important ordering detail to reduce races with the summary cron job:

- Create the `OpenRouterSummary(status='processing')` row *before* setting the document `processing_status='completed'` (or at least immediately after), so that a summary cron run does not observe “completed + no summary row” and start an OpenRouter call concurrently.

### F. Update cron scripts to respect the new recovery timestamp

1. `scripts/process_verapdf_jobs.py`
   - Update `find_pending_jobs()` to include the “stuck processing recovery threshold” logic.
   - When setting `processing_status='processing'`, also set `processing_started_at=now()`.

2. `scripts/process_openrouter_summaries.py`
   - No behavioral change is required for sync timeouts *if* the web request sets timed-out summaries back to `pending`.
   - Optionally, refactor to import the extracted `openrouter_helpers.py` module.

### G. Tests to add (minimal but meaningful)

Use the existing Django test runner (`uv run ./run_tests.py`).

Add tests covering:

1. **Sync success path**
   - Patch `pdf_helpers.run_verapdf` to return a small known JSON payload.
   - Patch OpenRouter helper to return a known OpenRouter response.
   - Assert:
     - `PDFDocument.processing_status == 'completed'`
     - `VeraPDFResult` exists
     - `OpenRouterSummary.status == 'completed'`

2. **veraPDF timeout → fallback**
   - Patch `run_verapdf` to raise `VeraPDFTimeoutError`.
   - Assert:
     - `PDFDocument.processing_status == 'pending'` (or `processing`, if you choose that semantics)
     - no `VeraPDFResult` row exists

3. **OpenRouter timeout → summary fallback**
   - Patch `run_verapdf` to succeed.
   - Patch OpenRouter helper to raise `httpx.TimeoutException` (or your wrapper).
   - Assert:
     - document is `completed`
     - summary is `pending` (cron can pick it up)

4. **Cron selection logic**
   - Create:
     - one doc in `processing` with `processing_started_at=now()` (should be skipped)
     - one doc in `processing` with `processing_started_at=now() - 20min` (should be selected)
   - Assert `find_pending_jobs()` selection matches expectations.

### H. Programmatic implementation sequence (low-risk)

1. **Add DB field + migration**
   - Edit `pdf_checker_app/models.py` to add `processing_started_at`.
   - Run:
     - `uv run python manage.py makemigrations pdf_checker_app --name add_processing_started_at`
     - `uv run python manage.py migrate`

2. **Update helper function(s)**
   - Modify `pdf_helpers.run_verapdf()` to support timeout and raise `VeraPDFTimeoutError`.
   - Add (or refactor into) `openrouter_helpers.py` used by both view + cron.

3. **Update cron script**
   - Implement “stuck processing” recovery threshold logic.
   - Ensure cron sets `processing_started_at` on start.

4. **Update upload view**
   - Add sync attempt logic with branching on timeout vs exception vs success.
   - Keep redirect-to-report behavior unchanged.

5. **Update tests**
   - Add tests described above.
   - Run: `uv run ./run_tests.py`.

6. **Deployment**
   - Ensure `.env` includes the OpenRouter variables so the sync attempt can run in the web process as well (or accept “no key → fallback”).

## Acceptance criteria (checklist)

- Upload still returns quickly when timeouts are hit (no request “hang” beyond 30 seconds per stage).
- If veraPDF completes within 30 seconds:
  - veraPDF section appears immediately (no waiting for cron).
- If OpenRouter completes within 30 seconds:
  - summary appears immediately.
- If either stage times out:
  - report page loads and continues polling until cron fills in missing pieces.
- Cron does not double-process documents that are actively in a sync attempt (fresh `processing_started_at`).
- Test suite passes via `uv run ./run_tests.py`.
