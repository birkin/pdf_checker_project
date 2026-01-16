#!/usr/bin/env python
"""
Cron-driven script to process pending veraPDF jobs.

Finds PDFDocument rows in 'pending' or 'processing' state, runs veraPDF,
and updates the database with results.

Usage:
    uv run ./scripts/process_verapdf_jobs.py [--batch-size N] [--dry-run]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

## Django setup - must happen before importing Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

## Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import django  # noqa: E402

django.setup()

from django.conf import settings as project_settings  # noqa: E402
from django.db import transaction  # noqa: E402

from pdf_checker_app.lib import pdf_helpers  # noqa: E402
from pdf_checker_app.models import PDFDocument  # noqa: E402

log = logging.getLogger(__name__)


def find_pending_jobs(batch_size: int) -> list[PDFDocument]:
    """
    Finds PDFDocument rows that need processing.
    Uses select_for_update with skip_locked to avoid double-processing.
    """
    with transaction.atomic():
        jobs = list(
            PDFDocument.objects.select_for_update(skip_locked=True)
            .filter(processing_status__in=['pending', 'processing'])
            .order_by('uploaded_at')[:batch_size]
        )
    return jobs


def process_single_job(doc: PDFDocument, verapdf_path: Path) -> bool:
    """
    Processes a single PDFDocument with veraPDF.
    Returns True on success, False on failure.
    """
    log.info(f'Processing document {doc.pk} ({doc.original_filename})')

    ## Mark as processing
    doc.processing_status = 'processing'
    doc.processing_error = None
    doc.save(update_fields=['processing_status', 'processing_error'])

    ## Resolve PDF path from checksum
    upload_dir = Path(project_settings.PDF_UPLOAD_PATH).resolve()
    pdf_path = upload_dir / f'{doc.file_checksum}.pdf'

    if not pdf_path.exists():
        error_msg = f'PDF file not found: {pdf_path}'
        log.error(error_msg)
        doc.processing_status = 'failed'
        doc.processing_error = error_msg
        doc.save(update_fields=['processing_status', 'processing_error'])
        return False

    success = False
    try:
        ## Run veraPDF
        log.debug(f'Running veraPDF on {pdf_path}')
        verapdf_raw_json = pdf_helpers.run_verapdf(pdf_path, verapdf_path)

        ## Parse output
        parsed_output = pdf_helpers.parse_verapdf_output(verapdf_raw_json)

        ## Persist result
        pdf_helpers.save_verapdf_result(doc.id, parsed_output)

        ## Mark as completed
        doc.processing_status = 'completed'
        doc.processing_error = None
        doc.save(update_fields=['processing_status', 'processing_error'])

        log.info(f'Successfully processed document {doc.pk}')
        success = True

    except Exception as exc:
        log.exception(f'Failed to process document {doc.pk}')
        doc.processing_status = 'failed'
        doc.processing_error = str(exc)
        doc.save(update_fields=['processing_status', 'processing_error'])

    return success


def process_jobs(batch_size: int, dry_run: bool) -> tuple[int, int]:
    """
    Finds and processes pending veraPDF jobs.
    Returns (success_count, failure_count).
    """
    verapdf_path = Path(project_settings.VERAPDF_PATH)

    jobs = find_pending_jobs(batch_size)
    log.info(f'Found {len(jobs)} jobs to process')

    if dry_run:
        for doc in jobs:
            log.info(f'[DRY RUN] Would process: {doc.pk} ({doc.original_filename})')
        return (0, 0)

    success_count = 0
    failure_count = 0

    for doc in jobs:
        if process_single_job(doc, verapdf_path):
            success_count += 1
        else:
            failure_count += 1

    return (success_count, failure_count)


def main() -> None:
    """
    Entry point for the cron script.
    """
    parser = argparse.ArgumentParser(description='Process pending veraPDF jobs')
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Maximum number of jobs to process in one run (default: 5)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually processing',
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
        format='[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    log.info('Starting veraPDF job processor')
    success_count, failure_count = process_jobs(args.batch_size, args.dry_run)
    log.info(f'Finished: {success_count} succeeded, {failure_count} failed')


if __name__ == '__main__':
    main()
