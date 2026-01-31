"""
Synchronous PDF processing helpers with timeout fallback.
Handles veraPDF and OpenRouter processing attempts with graceful degradation.

Called by:
    - pdf_checker_app.views.upload_pdf()
"""

import datetime
import logging
from pathlib import Path

import httpx
from django.conf import settings as project_settings
from django.utils import timezone as django_timezone

from pdf_checker_app.lib import openrouter_helpers, pdf_helpers
from pdf_checker_app.lib.pdf_helpers import VeraPDFTimeoutError
from pdf_checker_app.models import OpenRouterSummary, PDFDocument, VeraPDFResult

log = logging.getLogger(__name__)


def attempt_synchronous_processing(doc: PDFDocument, pdf_path: Path) -> None:
    """
    Attempts to run veraPDF and OpenRouter synchronously with timeouts.
    Updates doc status in-place. Falls back to 'pending' on timeout.
    """
    ## Mark as processing and set timestamp
    doc.processing_status = 'processing'
    doc.processing_error = None
    doc.processing_started_at = datetime.datetime.now()
    doc.save(update_fields=['processing_status', 'processing_error', 'processing_started_at'])

    ## Attempt veraPDF with timeout
    verapdf_success = attempt_verapdf_sync(doc, pdf_path)

    if not verapdf_success:
        return

    ## If veraPDF succeeded, attempt OpenRouter
    verapdf_result = VeraPDFResult.objects.get(pdf_document=doc)
    if verapdf_result.is_accessible:
        log.info(f'Skipping OpenRouter for accessible document {doc.pk}')
        return

    attempt_openrouter_sync(doc)


def attempt_verapdf_sync(doc: PDFDocument, pdf_path: Path) -> bool:
    """
    Attempts synchronous veraPDF processing with timeout.
    Returns True if successful, False if timeout or error.
    """
    verapdf_path = Path(project_settings.VERAPDF_PATH)
    timeout_seconds = project_settings.VERAPDF_SYNC_TIMEOUT_SECONDS

    try:
        log.info(f'Attempting synchronous veraPDF for document {doc.pk}')
        raw_output = pdf_helpers.run_verapdf(pdf_path, verapdf_path, timeout_seconds=timeout_seconds)
        parsed_output = pdf_helpers.parse_verapdf_output(raw_output)
        pdf_helpers.save_verapdf_result(doc.id, parsed_output)

        doc.processing_status = 'completed'
        doc.processing_error = None
        doc.save(update_fields=['processing_status', 'processing_error'])
        log.info(f'Synchronous veraPDF succeeded for document {doc.pk}')
        return True

    except VeraPDFTimeoutError:
        log.warning(f'veraPDF timed out for document {doc.pk}, falling back to cron')
        doc.processing_status = 'pending'
        doc.processing_started_at = None
        doc.save(update_fields=['processing_status', 'processing_started_at'])
        return False

    except Exception as exc:
        log.exception(f'veraPDF failed for document {doc.pk}')
        doc.processing_status = 'failed'
        doc.processing_error = str(exc)
        doc.save(update_fields=['processing_status', 'processing_error'])
        return False


def attempt_openrouter_sync(doc: PDFDocument) -> bool:
    """
    Attempts synchronous OpenRouter summary generation with timeout.
    Returns True if successful, False if timeout or error.
    """
    api_key = openrouter_helpers.get_api_key()
    model_order = openrouter_helpers.get_model_order()

    if not api_key or not model_order:
        log.warning(f'OpenRouter credentials not available, skipping sync attempt for document {doc.pk}')
        return False

    timeout_seconds = project_settings.OPENROUTER_SYNC_TIMEOUT_SECONDS

    ## Create summary record with 'processing' status BEFORE calling API
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    naive_now = django_timezone.make_naive(utc_now)
    summary, created = OpenRouterSummary.objects.get_or_create(
        pdf_document=doc,
        defaults={'status': 'processing', 'requested_at': naive_now},
    )

    if not created:
        summary.status = 'processing'
        summary.requested_at = naive_now
        summary.error = None
        summary.save(update_fields=['status', 'requested_at', 'error'])

    try:
        log.info(f'Attempting synchronous OpenRouter for document {doc.pk}')

        ## Get veraPDF result
        verapdf_result = VeraPDFResult.objects.get(pdf_document=doc)
        raw_verapdf_json = verapdf_result.raw_json

        ## Prune and build prompt
        verapdf_json = openrouter_helpers.filter_down_failure_checks(raw_verapdf_json)
        prompt = openrouter_helpers.build_prompt(verapdf_json)

        ## Save prompt
        summary.prompt = prompt
        summary.save(update_fields=['prompt'])

        ## Call API with timeout
        response_json = openrouter_helpers.call_openrouter_with_model_order(
            prompt,
            api_key,
            model_order,
            timeout_seconds,
        )
        parsed = openrouter_helpers.parse_openrouter_response(response_json)

        ## Persist
        openrouter_helpers.persist_openrouter_summary(summary, response_json, parsed)
        log.info(f'Synchronous OpenRouter succeeded for document {doc.pk}')
        return True

    except httpx.TimeoutException:
        log.warning(f'OpenRouter timed out for document {doc.pk}, falling back to cron')
        summary.status = 'pending'
        summary.error = 'Sync attempt timed out; will retry in background.'
        summary.save(update_fields=['status', 'error'])
        return False

    except Exception as exc:
        log.exception(f'OpenRouter failed for document {doc.pk}')
        summary.status = 'failed'
        summary.error = str(exc)
        summary.save(update_fields=['status', 'error'])
        return False
