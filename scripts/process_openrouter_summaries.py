#!/usr/bin/env python
"""
Cron-driven script to generate OpenRouter summaries for completed veraPDF results.

Finds PDFDocument rows with completed veraPDF processing but no summary,
calls OpenRouter API, and persists the results.

Usage:
    uv run ./scripts/process_openrouter_summaries.py [--batch-size N] [--dry-run]

Requires:
    OPENROUTER_API_KEY environment variable to be set.
    OPENROUTER_MODEL_ORDER environment variable to be set.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

## Django setup - must happen before importing Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

## Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

## Load environment variables
log = logging.getLogger(__name__)
dotenv_path = project_root.parent / '.env'
if dotenv_path.exists():
    load_dotenv(str(dotenv_path), override=True)
else:
    log.debug(f'.env file not found at {dotenv_path}; skipping dotenv load')

import django  # noqa: E402

django.setup()

from django.conf import settings as project_settings  # noqa: E402
from django.db.models import Q  # noqa: E402
from django.utils import timezone as django_timezone  # noqa: E402

from pdf_checker_app.lib import openrouter_helpers  # noqa: E402
from pdf_checker_app.models import OpenRouterSummary, PDFDocument, VeraPDFResult  # noqa: E402


def get_api_key() -> str:
    """
    Retrieves the OpenRouter API key from environment.
    """
    return openrouter_helpers.get_api_key()


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
        .exclude(verapdf_result__is_accessible=True)
        .order_by('uploaded_at')[:batch_size]
    )

    ## Find docs with pending or failed summary
    docs_with_pending_summary = (
        PDFDocument.objects.filter(
            processing_status='completed',
        )
        .filter(Q(openrouter_summary__status='pending') | Q(openrouter_summary__status='failed'))
        .filter(verapdf_result__isnull=False)
        .exclude(verapdf_result__is_accessible=True)
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


def get_model_order() -> list[str]:
    """
    Retrieves the OpenRouter model order from environment.
    """
    return openrouter_helpers.get_model_order()


def process_single_summary(doc: PDFDocument, api_key: str, model_order: list[str]) -> bool:
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
        verapdf_json = openrouter_helpers.filter_down_failure_checks(raw_verapdf_json)

        ## Build prompt
        prompt = openrouter_helpers.build_prompt(verapdf_json)
        log.debug(f'Calling OpenRouter for document {doc.pk}')

        ## Save prompt
        summary.prompt = prompt
        summary.save(update_fields=['prompt'])

        ## Call API with cron timeout
        timeout_seconds = project_settings.OPENROUTER_CRON_TIMEOUT_SECONDS
        response_json = openrouter_helpers.call_openrouter_with_model_order(
            prompt,
            api_key,
            model_order,
            timeout_seconds,
        )

        ## Parse response
        parsed = openrouter_helpers.parse_openrouter_response(response_json)

        ## Persist summary
        openrouter_helpers.persist_openrouter_summary(summary, response_json, parsed)

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

    model_order = get_model_order()
    if not model_order:
        log.error('OPENROUTER_MODEL_ORDER environment variable not set')
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
        if process_single_summary(doc, api_key, model_order):
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
