# Plan: move OpenRouter prompt to prompt.md

Review `pdf_checker_project/AGENTS.md` for coding-directives to follow.

## Goal
Move the OpenRouter prompt currently embedded in `pdf_checker_app/lib/openrouter_helpers.py` into a standalone Markdown file so prompt diffs are easy to track.

## Context
- The prompt is currently hardcoded as the `PROMPT` constant in `pdf_checker_app/lib/openrouter_helpers.py` and interpolated in `build_prompt()`.
- This prompt includes a `{verapdf_json_output}` placeholder.

## Assumptions
- The prompt content should remain identical (only the storage location changes).
- `build_prompt()` should still format with `verapdf_json_output` to preserve current behavior.
- File should live at `pdf_checker_app/lib/prompt.md` and be tracked in git.

## Implementation plan
1. **Add prompt file**
   - Create `pdf_checker_app/lib/prompt.md` and move the current `PROMPT` contents into it verbatim.
   - Keep the `{verapdf_json_output}` placeholder in the file.
   - Ensure the file uses LF line endings and no BOM.

2. **Load prompt from file**
   - In `openrouter_helpers.py`, replace the `PROMPT` constant with logic that reads `prompt.md` (e.g., in a new helper function like `load_prompt_template()` or inside `build_prompt()`).
   - Use a path relative to `openrouter_helpers.py` so the file resolves correctly in different working directories (e.g., `Path(__file__).resolve().parent / 'prompt.md'`).
   - Read as UTF-8 text and return a `str`.

3. **Update prompt building**
   - Update `build_prompt()` to use the loaded template instead of the constant.
   - Keep the existing formatting and logging behavior.

4. **Tests/verification**
   - If there are tests for prompt content or OpenRouter payloads, update expected values if needed.
   - Run `uv run ./run_tests.py`.
   - Optionally add a focused test for `build_prompt()` to ensure `{verapdf_json_output}` is interpolated.

5. **Update docs**
   - Update `pdf_checker_project/README.md` to reflect the new github prompt location -- and no need to have the link be a permalink.

## Implementation status
- Completed steps 1-5.
- New prompt file: `pdf_checker_app/lib/prompt.md`.
- `openrouter_helpers.py` now loads the prompt template from disk.
- README links to `prompt.md`.

## Notes for future session
- The prompt text is currently in `openrouter_helpers.py` as `PROMPT` (lines 23-48).
- `build_prompt()` currently formats the prompt with `json.dumps(..., indent=2)` and `.format()`.
- `call_openrouter()` builds the payload with `{'role': 'user', 'content': prompt}` and does not need changes.
