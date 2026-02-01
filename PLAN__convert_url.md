# Plan: convert `DYNAMIC_ABOUT_URL` in pattern-library header to correct Django URL

Before any code-changes, review `pdf_checker_project/AGENTS.md` for coding-directives to follow.

## Goal
Replace the literal string `DYNAMIC_ABOUT_URL` (appears twice in the generated pattern header include) with a URL that correctly points to the Django `info_url` endpoint in both:

- `runserver` local dev (no `/pdf_checker` prefix)
- Passenger deployment (must include `/pdf_checker` prefix)

User-update: I've updated the literal string `DYNAMIC_ABOUT_URL` to `{% url 'info_url' %}` in both places for the "About" link. Note that I made an "About2" link as a backup, that has also has an original-sytle `DYNAMIC_ABOUT_URL` placeholder. Ignore the "About2" link for now.

## Current state (repo facts)
- The placeholder appears twice in:
  - `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes/pattern_header/body.html`
    - Once in the “hamburger menu” About link
    - Once in the subheader About link
- That file is included from the Django base template:
  - `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/base.html` includes `.../pattern_header/body.html`
  - Therefore `body.html` is processed as a Django template (template tags will render).
- The target endpoint exists and is named:
  - `config/urls.py`: `path('info/', views.info, name='info_url')`

## Key deployment nuance (runserver vs Passenger)
Django URL reversing can automatically include a mount-prefix (like `/pdf_checker`) if Django is configured with a script prefix.

The two common ways this happens:
- **Preferred (automatic)**: the WSGI server sets `SCRIPT_NAME` (or equivalent), and Django sets the script prefix per request.
- **Fallback**: set `FORCE_SCRIPT_NAME="/pdf_checker"` in production settings/env.

If either of those is in place, `{% url 'info_url' %}` will generate:
- `/info/` on runserver
- `/pdf_checker/info/` when mounted under `/pdf_checker`

So the plan below is to rely on Django’s native reversing rather than hardcoding server-specific paths.

## Recommended implementation approach (robust against header re-fetches)
Because `body.html` is produced by the management command `update_pattern_header`, manual edits can be overwritten. So the durable fix is:

1. Update the pattern-header update pipeline to convert placeholders into Django template markup during generation.
2. Keep the upstream snapshot (`lib/pattern_header_upstream.html`) unchanged (it remains a “raw” capture).

### Step 1: Add placeholder replacement during header generation
- In `pdf_checker_app/management/commands/update_pattern_header.py`, after `split_pattern_header()` returns `body_content`, do a string replacement on the body fragment before saving:

  - Replace `DYNAMIC_ABOUT_URL` with the Django template tag:
    - `{% url 'info_url' %}`

  This keeps link generation authoritative and environment-aware.

  User-update: I've attempted to do this. Not sure if the single/double quotes are correct, but let's see if it works.

Notes:
- The `{% url %}` tag is available by default; you do not need to add `{% load %}`.
- This approach does **not** require touching every view’s `context`.

### Step 2: (Optional, but likely desirable) Replace other placeholders similarly

User-update: I know the pattern-library header also contains other placeholders:
- `DYNAMIC_CHECK-PDF_URL`
- `DYNAMIC__SITE`

But these are temporarily out-of-scope for this task -- so ignore those.

Note that I made an "About2" link as a backup, that has also has an original-sytle `DYNAMIC_ABOUT_URL` placeholder. Ignore the "About2" link for now.

### Step 3: Add/adjust tests
Add a focused test in `pdf_checker_app/tests/` validating the replacement behavior (separate from the existing split test):
- Given a minimal `body_content` string containing `DYNAMIC_ABOUT_URL`, assert the post-processing output contains `{% url 'info_url' %}` and does not contain `DYNAMIC_ABOUT_URL`.

This prevents regressions if the update command is edited later.

### Step 4: Verify mounted-prefix behavior in Passenger
If Passenger deployment currently **does not** automatically include `/pdf_checker` in reversed URLs, implement the fallback:
- Add `FORCE_SCRIPT_NAME` to production settings via environment variable (only on the server), e.g. `FORCE_SCRIPT_NAME="/pdf_checker"`.

User-update: I know the server-deployment already sets `pdf_checker` properly.

This does not need to be enabled for runserver.

## Alternative approach (if you explicitly want context-driven substitution)
If you prefer passing a value from each view (or via a context processor), then:

- Replace `DYNAMIC_ABOUT_URL` with a Django variable in the generated template, e.g.:
  - `{{ pattern_header_about_url }}`

and provide `pattern_header_about_url` via:
- **Best**: a context processor (so you don’t have to touch every view)
- **Acceptable but noisy**: add the variable to each view’s render context

In that context-driven approach, I recommend the placeholder name:
- `pattern_header_about_url`

because it’s specific enough to avoid collisions.

User-update: we will avoid this alternative approach for now.

## Acceptance checks
- In dev (runserver): About link points to `/info/`.
- In Passenger deployment under `/pdf_checker`: About link points to `/pdf_checker/info/`.
- Running `update_pattern_header` does not reintroduce `DYNAMIC_ABOUT_URL` into the saved include.
