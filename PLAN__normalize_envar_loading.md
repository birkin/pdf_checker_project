# PLAN: Normalize env var loading/handling

## Goal
Normalize environment variable loading so `.env` is only loaded in Django settings files, and other modules rely on Django settings rather than direct `os.environ` access.

## Context snapshot (current state)

### Settings files
- `config/settings.py` currently loads `.env` directly via `dotenv` and reads many env vars (e.g., `SECRET_KEY`, `DEBUG_JSON`, `LOG_PATH`, `VERAPDF_PATH`, `PDF_UPLOAD_PATH`). @pdf_checker_project/config/settings.py#13-223
- `config/settings_ci_tests.py` does not load `.env` and uses hard-coded test values for CI. @pdf_checker_project/config/settings_ci_tests.py#1-235

### Direct env var access outside settings
- OpenRouter helpers read from `os.environ`:
  - `OPENROUTER_API_KEY` / `OPENROUTER_MODEL_ORDER`. @pdf_checker_project/pdf_checker_app/lib/openrouter_helpers.py#51-65
  - Optional `SYSTEM_CA_BUNDLE` inside API call. @pdf_checker_project/pdf_checker_app/lib/openrouter_helpers.py#119-144
- Scripts use environment vars only for Django settings module selection (and one script loads `.env` itself):
  - `scripts/process_openrouter_summaries.py` loads `.env` directly and sets `DJANGO_SETTINGS_MODULE`. @pdf_checker_project/scripts/process_openrouter_summaries.py#23-38
  - `scripts/process_verapdf_jobs.py` sets `DJANGO_SETTINGS_MODULE`, no dotenv. @pdf_checker_project/scripts/process_verapdf_jobs.py#19-30
- Test runner uses env vars for `GITHUB_ACTIONS` + `DJANGO_SETTINGS_MODULE`. @pdf_checker_project/run_tests.py#31-72
- Django bootstrap files set `DJANGO_SETTINGS_MODULE` via `os.environ`. @pdf_checker_project/manage.py#10-31, @pdf_checker_project/config/wsgi.py#10-23

### .env example
- `config/dotenv_example_file.txt` documents project-level env vars used by settings. @pdf_checker_project/config/dotenv_example_file.txt#1-82

## Plan

### 1) Identify env vars that should be settings-owned
Create a short list of env vars currently accessed outside settings, and decide the canonical settings name for each.
- **OpenRouter**:
  - `OPENROUTER_API_KEY` -> `OPENROUTER_API_KEY` in settings.
  - `OPENROUTER_MODEL_ORDER` -> `OPENROUTER_MODEL_ORDER` in settings as a `list[str]` (parse CSV in settings, not in lib).
- **TLS/CA bundle**:
  - `SYSTEM_CA_BUNDLE` -> `SYSTEM_CA_BUNDLE` (or `OPENROUTER_CA_BUNDLE`) in settings.

Add these settings to both `config/settings.py` and `config/settings_ci_tests.py` with appropriate defaults for CI (likely empty string / empty list).

### 2) Centralize dotenv loading in settings
- Keep `.env` loading only in `config/settings.py`.
- Remove dotenv loading in `scripts/process_openrouter_summaries.py`.
  - Rationale: scripts already set `DJANGO_SETTINGS_MODULE`, and settings handles dotenv.
  - If `.env` is missing, settings already asserts; decide whether to preserve/relax that behavior for scripts.

### 3) Replace direct env usage in application code
- Update `pdf_checker_app/lib/openrouter_helpers.py` to pull values from Django settings rather than `os.environ`:
  - `get_api_key()` -> `django.conf.settings.OPENROUTER_API_KEY`
  - `get_model_order()` -> `django.conf.settings.OPENROUTER_MODEL_ORDER`
  - `call_openrouter()` -> `django.conf.settings.SYSTEM_CA_BUNDLE`

### 4) Validate script impacts
- Both scripts import `django` and call `django.setup()` after setting `DJANGO_SETTINGS_MODULE`, so Django settings will be accessible.
- Removing dotenv load in the scripts should still work as long as `.env` is loaded in `config/settings.py`.
- Confirm there is no script usage that bypasses Django settings (e.g., runs before `django.setup()`); current flow looks safe.

Potential edge cases:
- `.env` missing for cron jobs: current `settings.py` asserts `.env` exists; removing script-level dotenv means the assertion will still fire. Decide whether to keep assertion or allow a fallback (e.g., pass in env vars from system).

### 5) GitHub CI considerations
- `run_tests.py` picks `config.settings_ci_tests` when `GITHUB_ACTIONS=true`. That settings module should include any new settings constants added in step 1.
- Ensure CI settings do not require `.env` load (still true), but add any new default values to keep imports stable.

### 6) Update documentation
- Add new env var entries to `config/dotenv_example_file.txt` for OpenRouter + CA bundle if they are not already included.
- If adding `OPENROUTER_MODEL_ORDER` parsing in settings, document the CSV format.

## Execution checklist (when implementing)
1. Add new settings in `config/settings.py` and `config/settings_ci_tests.py`.
2. Switch `openrouter_helpers.py` to use `django.conf.settings` instead of `os.environ`.
3. Remove dotenv loading from `scripts/process_openrouter_summaries.py`.
4. Update `.env` example file.
5. Run tests: `uv run ./run_tests.py`.

## Notes for a fresh work session
- This repo expects Django settings to be the sole env var loader (`dotenv` in settings). The goal is to align all code with that pattern.
- `settings.py` currently asserts the `.env` file exists; decide if cron workflows should rely on that or accept system-provided vars.
- Scripts are run via `uv run ./scripts/...` per AGENTS.md; ensure any changes keep that working.
