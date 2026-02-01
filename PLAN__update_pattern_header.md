---
description: Plan to fix pattern header link extraction
---

# PLAN__update_pattern_header

## Summary of findings
- The upstream HTML now includes the stylesheet link as `https://library.brown.edu/common/css/bul_patterns.css` (see `pdf_checker_app/lib/pattern_header_upstream.html` @ `/Users/birkin/Documents/Brown_Library/djangoProjects/pdf_checker_stuff/pdf_checker_project/pdf_checker_app/lib/pattern_header_upstream.html#16-16`).
- The parsing regex in `update_pattern_header.split_pattern_header()` only matches the older host `https://dlibwwwcit.services.brown.edu/common/css/bul_patterns.css` (see `pdf_checker_app/management/commands/update_pattern_header.py` @ `/Users/birkin/Documents/Brown_Library/djangoProjects/pdf_checker_stuff/pdf_checker_project/pdf_checker_app/management/commands/update_pattern_header.py#61-70`).
- Tests are also hard-coded to the older host (see `pdf_checker_app/tests/test_pattern_header.py` @ `/Users/birkin/Documents/Brown_Library/djangoProjects/pdf_checker_stuff/pdf_checker_project/pdf_checker_app/tests/test_pattern_header.py#12-57`).
- As a result, `head.html` is currently empty (see `pdf_checker_app_templates/pdf_checker_app/includes/pattern_header/head.html` @ `/Users/birkin/Documents/Brown_Library/djangoProjects/pdf_checker_stuff/pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes/pattern_header/head.html#1-1`).

## Goals
1. Ensure the `<link rel="stylesheet" ... bul_patterns.css ...>` tag is extracted to `head.html` for the new upstream host.
2. Keep parsing resilient to small attribute changes (spacing, attribute order, self-closing vs. not).
3. Update tests to cover the new upstream format and an edge case.

## Plan (code changes to implement in a later session)

Review `pdf_checker_project/AGENTS.md` for coding-directives to follow.

1. **Adjust `split_pattern_header()` matching logic.**
   - File: `pdf_checker_app/management/commands/update_pattern_header.py`.
   - Replace the regex that hard-codes `dlibwwwcit.services.brown.edu` with a more flexible pattern that matches any host but requires `/common/css/bul_patterns.css`.
   - Suggested regex update (example):
     - Match on `href="https://[^\"']+/common/css/bul_patterns\.css"` (case-insensitive), still capturing the full `<link ...>` tag.
   - Keep the behavior of pulling the first matching link tag into `head_content` and stripping only that first tag from `body_content`.

2. **Update tests to match the new upstream format and the new regex.**
   - File: `pdf_checker_app/tests/test_pattern_header.py`.
   - Update the expected `href` to `https://library.brown.edu/common/css/bul_patterns.css` for the main test.
   - Add an edge case test for attribute order or an alternate host (e.g., `https://library.brown.edu/common/css/bul_patterns.css?version=...` if upstream adds query params, or a different host to ensure the regex is host-agnostic). Keep the test minimal and aligned with how the regex will be updated.
   - Ensure test docstrings continue to start with “Checks...”.

3. **(Optional) Add a small safeguard or logging if no link is found.**
   - Decide if the management command should emit a warning or error when `head_content` is empty, since this indicates the regex failed.
   - If adding output, keep it minimal and align with the command’s existing `stdout` pattern.

4. **Run tests / validation commands (later session).**
   - `uv run ./run_tests.py` (or narrow to the pattern header tests if `run_tests.py` supports it).
   - If running the management command manually after the fix: `uv run ./manage.py update_pattern_header --dry-run`.

## Context notes for future session
- The upstream `pattern_header_upstream.html` appears to be a snapshot captured from the remote pattern header source, and contains a `<link>` tag to the stylesheet on line ~16 using the new host (`library.brown.edu`).
- The current regex only matches the old host, so `head.html` becomes empty and `body.html` still contains the link tag. This implies the parsing should match the new host without breaking the original behavior.
- Keep `ruff.toml` style constraints in mind (single quotes, line-length 125) when editing Python files.

## Files to edit later
- `pdf_checker_app/management/commands/update_pattern_header.py`
- `pdf_checker_app/tests/test_pattern_header.py`

## Files to inspect when validating
- `pdf_checker_app/lib/pattern_header_upstream.html`
- `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes/pattern_header/head.html`
- `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes/pattern_header/body.html`
