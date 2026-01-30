import datetime
import json
import logging
import uuid
from pathlib import Path

import trio
from django.conf import settings as project_settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from pdf_checker_app.forms import PDFUploadForm
from pdf_checker_app.lib import pdf_helpers, sync_processing_helpers, version_helper
from pdf_checker_app.lib.version_helper import GatherCommitAndBranchData
from pdf_checker_app.models import OpenRouterSummary, PDFDocument, VeraPDFResult

log = logging.getLogger(__name__)

# -------------------------------------------------------------------
# htmx fragment endpoints for polling
# -------------------------------------------------------------------


def status_fragment(request, pk: uuid.UUID):
    """
    Returns a small HTML fragment for the status area.
    Used by htmx polling on the report page.
    Stops polling when processing is complete or failed.
    """
    log.debug(f'starting status_fragment() for pk={pk}')
    doc = get_object_or_404(PDFDocument, pk=pk)

    ## Determine if we should continue polling
    is_terminal = doc.processing_status in ('completed', 'failed')

    response = render(
        request,
        'pdf_checker_app/fragments/status_fragment.html',
        {
            'document': doc,
            'is_terminal': is_terminal,
        },
    )
    response['Cache-Control'] = 'no-store'
    return response


def verapdf_fragment(request, pk: uuid.UUID):
    """
    Returns an HTML fragment for the veraPDF results section.
    Called once when status indicates veraPDF is ready.
    """
    log.debug(f'starting verapdf_fragment() for pk={pk}')
    doc = get_object_or_404(PDFDocument, pk=pk)

    verapdf_raw_json: str | None = None
    if doc.processing_status == 'completed':
        verapdf_raw_json_data = VeraPDFResult.objects.filter(pdf_document=doc).values_list('raw_json', flat=True).first()
        if verapdf_raw_json_data is not None:
            verapdf_raw_json = json.dumps(verapdf_raw_json_data, indent=2)

    response = render(
        request,
        'pdf_checker_app/fragments/verapdf_fragment.html',
        {
            'document': doc,
            'verapdf_raw_json': verapdf_raw_json,
        },
    )
    response['Cache-Control'] = 'no-store'
    return response


def summary_fragment(request, pk: uuid.UUID):
    """
    Returns an HTML fragment for the OpenRouter summary section.
    Can be polled or loaded once depending on UX preference.
    """
    log.debug(f'starting summary_fragment() for pk={pk}')
    doc = get_object_or_404(PDFDocument, pk=pk)

    suggestions: OpenRouterSummary | None = None
    try:
        suggestions = doc.openrouter_summary
    except OpenRouterSummary.DoesNotExist:
        pass

    response = render(
        request,
        'pdf_checker_app/fragments/summary_fragment.html',
        {
            'document': doc,
            'suggestions': suggestions,
        },
    )
    response['Cache-Control'] = 'no-store'
    return response


# -------------------------------------------------------------------
# main urls
# -------------------------------------------------------------------


def info(request):
    """
    The "about" view.
    Can get here from 'info' url, and the root-url redirects here.
    """
    log.debug('starting info()')
    ## prep data ----------------------------------------------------
    # context = { 'message': 'Hello, world.' }
    context = {
        'quote': 'The best life is the one in which the creative impulses play the largest part and the possessive impulses the smallest.',
        'author': 'Bertrand Russell',
    }
    ## prep response ------------------------------------------------
    if request.GET.get('format', '') == 'json':
        log.debug('building json response')
        resp = HttpResponse(
            json.dumps(context, sort_keys=True, indent=2),
            content_type='application/json; charset=utf-8',
        )
    else:
        log.debug('building template response')
        resp = render(request, 'info.html', context)
    return resp


# -------------------------------------------------------------------
# support urls
# -------------------------------------------------------------------


def error_check(request):
    """
    Offers an easy way to check that admins receive error-emails (in development).
    To view error-emails in runserver-development:
    - run, in another terminal window: `python -m smtpd -n -c DebuggingServer localhost:1026`,
    - (or substitue your own settings for localhost:1026)
    """
    log.debug('starting error_check()')
    log.debug(f'project_settings.DEBUG, ``{project_settings.DEBUG}``')
    if project_settings.DEBUG is True:  # localdev and dev-server; never production
        log.debug('triggering exception')
        raise Exception('Raising intentional exception to check email-admins-on-error functionality.')
    else:
        log.debug('returning 404')
        return HttpResponseNotFound('<div>404 / Not Found</div>')


def version(request):
    """
    Returns basic branch and commit data.
    """
    log.debug('starting version()')
    rq_now = datetime.datetime.now()
    gatherer = GatherCommitAndBranchData()
    trio.run(gatherer.manage_git_calls)
    info_txt = f'{gatherer.branch} {gatherer.commit}'
    context = version_helper.make_context(request, rq_now, info_txt)
    output = json.dumps(context, sort_keys=True, indent=2)
    log.debug(f'output, ``{output}``')
    return HttpResponse(output, content_type='application/json; charset=utf-8')


def root(request):
    return HttpResponseRedirect(reverse('info_url'))


# -------------------------------------------------------------------
# pdf upload and processing
# -------------------------------------------------------------------


def upload_pdf(request: HttpRequest) -> HttpResponse:
    """
    Handles PDF upload with synchronous processing attempt.

    Attempts to run veraPDF and OpenRouter synchronously with timeouts.
    Falls back to polling + cron if timeouts are hit.
    """
    log.debug('\n\nstarting upload_pdf()\n\n')
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']

            ## Get Shibboleth user info
            user_info: dict[str, str | list[str]] = pdf_helpers.get_shibboleth_user_info(request)

            ## Generate checksum
            checksum: str = pdf_helpers.generate_checksum(pdf_file)

            ## Check if already processed
            existing_doc: PDFDocument | None = PDFDocument.objects.filter(file_checksum=checksum).first()

            if existing_doc and existing_doc.processing_status == 'completed':
                messages.info(request, 'This PDF has already been processed.')
                return HttpResponseRedirect(reverse('pdf_report_url', kwargs={'pk': existing_doc.pk}))

            ## For pending/processing docs, redirect to report (let polling handle it)
            if existing_doc and existing_doc.processing_status in ('pending', 'processing'):
                messages.info(request, 'This PDF is already being processed.')
                return HttpResponseRedirect(reverse('pdf_report_url', kwargs={'pk': existing_doc.pk}))

            ## For failed docs, allow re-upload by resetting to pending
            if existing_doc and existing_doc.processing_status == 'failed':
                doc: PDFDocument = existing_doc
                doc.processing_status = 'pending'
                doc.processing_error = None
                doc.save(update_fields=['processing_status', 'processing_error'])
            else:
                ## Create new document record with Shibboleth user info
                doc: PDFDocument = PDFDocument.objects.create(
                    original_filename=pdf_file.name,
                    file_checksum=checksum,
                    file_size=pdf_file.size,
                    user_first_name=user_info['first_name'],
                    user_last_name=user_info['last_name'],
                    user_email=user_info['email'],
                    user_groups=user_info['groups'],
                    processing_status='pending',
                )

            ## Save file
            try:
                pdf_path: Path = pdf_helpers.save_pdf_file(pdf_file, checksum)
                log.debug(f'saved PDF file to {pdf_path}')
            except Exception as exc:
                log.exception('Failed to save PDF file')
                doc.processing_status = 'failed'
                doc.processing_error = f'Failed to save file: {exc}'
                doc.save(update_fields=['processing_status', 'processing_error'])
                messages.error(request, 'Failed to save PDF file. Please try again.')
                return HttpResponseRedirect(reverse('pdf_report_url', kwargs={'pk': doc.pk}))

            ## Attempt synchronous processing
            sync_processing_helpers.attempt_synchronous_processing(doc, pdf_path)

            ## Redirect to report page
            if doc.processing_status == 'completed':
                messages.success(request, 'PDF processed successfully!')
            else:
                messages.success(request, 'PDF uploaded successfully. Processing in progress.')
            return HttpResponseRedirect(reverse('pdf_report_url', kwargs={'pk': doc.pk}))
    else:
        form: PDFUploadForm = PDFUploadForm()

    return render(request, 'pdf_checker_app/upload.html', {'form': form})

    ## end def upload_pdf()


def view_report(request, pk: uuid.UUID):
    """
    Displays the accessibility report for a processed PDF.
    """
    log.debug(f'starting view_report() for pk={pk}')
    doc = get_object_or_404(PDFDocument, pk=pk)
    verapdf_raw_json: str | None = None
    if doc.processing_status == 'completed':
        verapdf_raw_json_data = VeraPDFResult.objects.filter(pdf_document=doc).values_list('raw_json', flat=True).first()
        if verapdf_raw_json_data is not None:
            verapdf_raw_json = json.dumps(verapdf_raw_json_data, indent=2)

    ## Get OpenRouter summary if it exists
    suggestions: OpenRouterSummary | None = None
    try:
        suggestions = doc.openrouter_summary
    except OpenRouterSummary.DoesNotExist:
        pass

    return render(
        request,
        'pdf_checker_app/report.html',
        {
            'document': doc,
            'verapdf_raw_json': verapdf_raw_json,
            'suggestions': suggestions,
        },
    )
