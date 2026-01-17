#!/usr/bin/env python
"""
Cron-driven script to generate OpenRouter summaries for completed veraPDF results.

Finds PDFDocument rows with completed veraPDF processing but no summary,
calls OpenRouter API, and persists the results.

Usage:
    uv run ./scripts/process_openrouter_summaries.py [--batch-size N] [--dry-run]

Requires:
    OPENROUTER_API_KEY environment variable to be set.
    OPENROUTER_MODEL environment variable to be set.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

## Django setup - must happen before importing Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

## Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

## Load environment variables
dotenv_path = project_root.parent / '.env'
load_dotenv(find_dotenv(str(dotenv_path), raise_error_if_not_found=True), override=True)

import django  # noqa: E402

django.setup()

import httpx  # noqa: E402
from django.utils import timezone as django_timezone  # noqa: E402

from pdf_checker_app.models import OpenRouterSummary, PDFDocument, VeraPDFResult  # noqa: E402

log = logging.getLogger(__name__)

## OpenRouter configuration
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = os.environ['OPENROUTER_API_KEY']
OPENROUTER_MODEL = os.environ['OPENROUTER_MODEL']
OPENROUTER_TIMEOUT = 60.0  # seconds
PROMPT = """
# Context: 
- I ran a pdf accessibility report using veraPDF, using the `PDF/UA-1 - Accessibility (PDF 1.7)` profile.
- I got back this json output:

```
{verapdf_json_output}
```

# Task: 
- Imagine a user has uploaded this pdf to a customized pdf-accessibility checker.
- Imagine the user is not a developer, and not extremely technically savvy, but does have access to a couple of the most common pdf-editing tools like Acrobat.
- Analyze the validation-result json file above.
- Main task: Come up with some helpful suggestions to the user about how to start fixing the errors.

## Regarding your helpful-suggestions:
- Focus on the top three improvements that would give the most "bang for the buck", in terms of improving accessibility.
- Start the helpful-suggestions text like: "Here are some suggestions to improve the accessibility of your PDF."
- Do not mention or reference the report.
- It's ok to mention that there are other things that may need to be addressed, but the goal is to not overwhelm the user.
- Do not use jargon, like referring to "XMP". Instead, convey that some metadata needs to be improved.
- Do not invite followup questions.
- Do not include information the user will have seen. 
	- Here is information the user will have seen: ```Note: veraPDF may report thousands of "failed checks" -- but that does _not_ mean thousands of distinct problems. Think of a "failed check" as a repeated warning bell, not a separate task. Example: if the PDF lacks a language setting, or proper tagging, veraPDF will flag each affected text snippet or layout element, inflating totals. Remediation work should target a few root causes, which can clear thousands of checks quickly.```
	- So do not reiterate that information in your helpful-suggestions.
"""


def get_api_key() -> str:
    """
    Retrieves the OpenRouter API key from environment.
    """
    return OPENROUTER_API_KEY


def find_pending_summaries(batch_size: int) -> list[PDFDocument]:
    """
    Finds PDFDocument rows that need summary generation.
    Criteria:
    - processing_status == 'completed'
    - has a VeraPDFResult
    - does NOT have an OpenRouterSummary OR has one with status 'pending'
    """
    ## Find docs with completed veraPDF but no summary
    docs_without_summary = (
        PDFDocument.objects.filter(processing_status='completed')
        .exclude(openrouter_summary__isnull=False)
        .filter(verapdf_result__isnull=False)
        .order_by('uploaded_at')[:batch_size]
    )

    ## Find docs with pending summary
    docs_with_pending_summary = (
        PDFDocument.objects.filter(processing_status='completed', openrouter_summary__status='pending')
        .filter(verapdf_result__isnull=False)
        .order_by('uploaded_at')[:batch_size]
    )

    ## Combine and deduplicate
    doc_ids = set()
    result: list[PDFDocument] = []
    for doc in list(docs_without_summary) + list(docs_with_pending_summary):
        if doc.pk not in doc_ids and len(result) < batch_size:
            doc_ids.add(doc.pk)
            result.append(doc)

    return result


def build_prompt(verapdf_json: dict) -> str:
    """
    Builds the prompt for OpenRouter based on veraPDF results.
    """
    import json

    verapdf_json_str = json.dumps(verapdf_json, indent=2)
    prompt = PROMPT.format(verapdf_json_output=verapdf_json_str)
    log.debug(f'prompt, ``{prompt}``')
    return prompt


# def build_prompt(verapdf_json: dict) -> str:
#     """
#     Builds the prompt for OpenRouter based on veraPDF results.
#     """
#     ## Extract key information from veraPDF JSON
#     summary_info = []

#     ## Try to extract summary statistics
#     if 'jobs' in verapdf_json and verapdf_json['jobs']:
#         job = verapdf_json['jobs'][0]
#         if 'validationResult' in job:
#             validation = job['validationResult']
#             summary_info.append(f'Profile: {validation.get("profileName", "Unknown")}')
#             summary_info.append(f'Compliant: {validation.get("compliant", "Unknown")}')

#             details = validation.get('details', {})
#             summary_info.append(f'Passed rules: {details.get("passedRules", 0)}')
#             summary_info.append(f'Failed rules: {details.get("failedRules", 0)}')
#             summary_info.append(f'Passed checks: {details.get("passedChecks", 0)}')
#             summary_info.append(f'Failed checks: {details.get("failedChecks", 0)}')

#     summary_text = '\n'.join(summary_info) if summary_info else 'No summary available'
#     log.debug(f'summary_text, ``{summary_text}``')

#     prompt = f"""You are an accessibility expert analyzing PDF/UA-1 validation results from veraPDF.

# Based on the following validation summary, provide a brief, helpful explanation for a document author who wants to make their PDF accessible:

# {summary_text}

# Please:
# 1. Explain what the results mean in plain language
# 2. If there are failures, explain the most common types of issues and how to fix them
# 3. Keep the response concise (2-3 paragraphs max)
# 4. Be encouraging - even many failures often stem from just a few root causes

# Note: The full veraPDF JSON contains detailed failure information, but focus on providing actionable guidance rather than listing every issue."""

#     log.debug(f'prompt, ``{prompt}``')
#     return prompt


def filter_down_failure_checks(raw_verapdf_json: dict) -> dict:
    """
    Filters down veraPDF JSON by keeping only one unique check per rule in 'checks' arrays.
    Uses the same logic as the prune_checks() function from filter_down_failure_checks.py.
    """
    return prune_checks_recursive(raw_verapdf_json)


def prune_checks_recursive(value: object) -> object:
    """
    Recursively processes the JSON, keeping one unique check per rule in 'checks' arrays.
    """
    pruned: object = value

    if isinstance(value, dict):
        new_dict: dict[str, object] = {}
        for key, child in value.items():
            if key == 'checks' and isinstance(child, list):
                new_dict[key] = filter_unique_checks(child)
            else:
                new_dict[key] = prune_checks_recursive(child)
        pruned = new_dict

    elif isinstance(value, list):
        new_list: list[object] = []
        for child in value:
            new_list.append(prune_checks_recursive(child))
        pruned = new_list

    return pruned


def filter_unique_checks(checks: list[object]) -> list[object]:
    """
    Filters a checks array to keep only one representative check.
    """
    if len(checks) > 0:
        return [checks[0]]
    return []


def call_openrouter(prompt: str, api_key: str) -> dict:
    """
    Calls the OpenRouter API with the given prompt.
    Returns the raw response JSON.
    """
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://library.brown.edu',
        'X-Title': 'PDF Accessibility Checker',
    }

    payload = {
        'model': OPENROUTER_MODEL,
        'messages': [
            {'role': 'user', 'content': prompt},
        ],
    }

    with httpx.Client(timeout=OPENROUTER_TIMEOUT) as client:
        response = client.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        jsn_response = response.json()
        log.debug(f'jsn_response, ``{jsn_response}``')
        return jsn_response


def parse_openrouter_response(response_json: dict) -> dict:
    """
    Parses the OpenRouter response and extracts relevant fields.
    """
    result = {
        'summary_text': '',
        'openrouter_response_id': response_json.get('id', ''),
        'provider': response_json.get('provider', ''),
        'model': response_json.get('model', ''),
        'finish_reason': '',
        'openrouter_created_at': None,
        'prompt_tokens': None,
        'completion_tokens': None,
        'total_tokens': None,
    }

    ## Extract summary text from choices
    choices = response_json.get('choices', [])
    if choices:
        choice = choices[0]
        message = choice.get('message', {})
        result['summary_text'] = message.get('content', '')
        result['finish_reason'] = choice.get('finish_reason', '')

    ## Extract usage info
    usage = response_json.get('usage', {})
    result['prompt_tokens'] = usage.get('prompt_tokens')
    result['completion_tokens'] = usage.get('completion_tokens')
    result['total_tokens'] = usage.get('total_tokens')

    ## Extract created timestamp
    created = response_json.get('created')
    if created:
        utc_dt = datetime.fromtimestamp(created, tz=timezone.utc)
        result['openrouter_created_at'] = django_timezone.make_naive(utc_dt)

    return result


def process_single_summary(doc: PDFDocument, api_key: str) -> bool:
    """
    Generates and saves an OpenRouter summary for a single document.
    Returns True on success, False on failure.
    Called by process_summaries()
    """
    log.info(f'Processing summary for document {doc.pk} ({doc.original_filename})')

    ## Get or create the summary record
    summary: OpenRouterSummary
    created: bool
    utc_now = datetime.now(tz=timezone.utc)
    naive_now = django_timezone.make_naive(utc_now)
    summary, created = OpenRouterSummary.objects.get_or_create(
        pdf_document=doc,
        defaults={'status': 'processing', 'requested_at': naive_now},
    )

    if not created:
        utc_now = datetime.now(tz=timezone.utc)
        naive_now = django_timezone.make_naive(utc_now)
        summary.status = 'processing'
        summary.requested_at = naive_now
        summary.error = None
        summary.save(update_fields=['status', 'requested_at', 'error'])

    success = False
    try:
        ## Get veraPDF result
        verapdf_result = VeraPDFResult.objects.get(pdf_document=doc)
        raw_verapdf_json = verapdf_result.raw_json

        ## Prune checks
        verapdf_json = filter_down_failure_checks(raw_verapdf_json)

        ## Build prompt
        prompt = build_prompt(verapdf_json)
        log.debug(f'Calling OpenRouter for document {doc.pk}')

        ## Save prompt
        summary.prompt_text = prompt
        summary.save(update_fields=['prompt_text'])

        ## Call API
        response_json = call_openrouter(prompt, api_key)

        ## Parse response
        parsed = parse_openrouter_response(response_json)

        ## Update summary record
        summary.raw_response_json = response_json
        summary.summary_text = parsed['summary_text']
        summary.openrouter_response_id = parsed['openrouter_response_id']
        summary.provider = parsed['provider']
        summary.model = parsed['model']
        summary.finish_reason = parsed['finish_reason']
        summary.openrouter_created_at = parsed['openrouter_created_at']
        summary.prompt_tokens = parsed['prompt_tokens']
        summary.completion_tokens = parsed['completion_tokens']
        summary.total_tokens = parsed['total_tokens']
        utc_now = datetime.now(tz=timezone.utc)
        naive_now = django_timezone.make_naive(utc_now)
        summary.status = 'completed'
        summary.completed_at = naive_now
        summary.error = None
        summary.save()

        log.info(f'Successfully generated summary for document {doc.pk}')
        success = True

    except Exception as exc:
        log.exception(f'Failed to generate summary for document {doc.pk}')
        summary.status = 'failed'
        summary.error = str(exc)
        summary.save(update_fields=['status', 'error'])

    return success


def process_summaries(batch_size: int, dry_run: bool) -> tuple[int, int]:
    """
    Finds and processes pending OpenRouter summaries.
    Returns (success_count, failure_count).
    """
    api_key = get_api_key()
    if not api_key:
        log.error('OPENROUTER_API_KEY environment variable not set')
        return (0, 0)

    docs = find_pending_summaries(batch_size)
    log.info(f'Found {len(docs)} documents needing summaries')

    if dry_run:
        for doc in docs:
            log.info(f'[DRY RUN] Would generate summary for: {doc.pk} ({doc.original_filename})')
        return (0, 0)

    success_count = 0
    failure_count = 0

    for doc in docs:
        if process_single_summary(doc, api_key):
            success_count += 1
        else:
            failure_count += 1

    return (success_count, failure_count)


def main() -> None:
    """
    Entry point for the cron script.
    """
    parser = argparse.ArgumentParser(description='Generate OpenRouter summaries for completed PDFs')
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1,
        help='Maximum number of summaries to generate in one run (default: 1)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually calling the API',
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging',
    )
    args = parser.parse_args()

    ## Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
        datefmt='%d/%b/%Y %H:%M:%S',
    )

    log.info('Starting OpenRouter summary processor')
    success_count, failure_count = process_summaries(args.batch_size, args.dry_run)
    log.info(f'Finished: {success_count} succeeded, {failure_count} failed')


if __name__ == '__main__':
    main()
