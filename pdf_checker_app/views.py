import datetime
import json
import logging

import trio
from django.conf import settings as project_settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from pdf_checker_app.forms import PDFUploadForm
from pdf_checker_app.lib import pdf_helpers, version_helper
from pdf_checker_app.lib.version_helper import GatherCommitAndBranchData
from pdf_checker_app.models import PDFDocument

log = logging.getLogger(__name__)


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


def upload_pdf(request):
    """
    Handles PDF upload and initiates processing.
    """
    log.debug('starting upload_pdf()')
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']

            ## Get Shibboleth user info
            user_info = pdf_helpers.get_shibboleth_user_info(request)

            ## Generate checksum
            checksum = pdf_helpers.generate_checksum(pdf_file)

            ## Check if already processed
            existing_doc = PDFDocument.objects.filter(file_checksum=checksum).first()

            if existing_doc and existing_doc.processing_status == 'completed':
                messages.info(request, 'This PDF has already been processed.')
                return HttpResponseRedirect(reverse('pdf_report_url', kwargs={'pk': existing_doc.pk}))

            ## Create new document record with Shibboleth user info
            if not existing_doc:
                doc = PDFDocument.objects.create(
                    original_filename=pdf_file.name,
                    file_checksum=checksum,
                    file_size=pdf_file.size,
                    user_first_name=user_info['first_name'],
                    user_last_name=user_info['last_name'],
                    user_email=user_info['email'],
                    user_groups=user_info['groups'],
                    processing_status='pending',
                )
            else:
                doc = existing_doc

            ## Save temporary file for processing
            temp_path = pdf_helpers.save_temp_file(pdf_file, checksum)
            log.debug(f'saved temp file to {temp_path}')

            ## TODO: Process with veraPDF (will be implemented separately)
            ## For now, just mark as pending and redirect
            messages.success(request, 'PDF uploaded successfully and queued for processing.')
            return HttpResponseRedirect(reverse('pdf_report_url', kwargs={'pk': doc.pk}))
    else:
        form = PDFUploadForm()

    return render(request, 'pdf_checker_app/upload.html', {'form': form})


def view_report(request, pk: int):
    """
    Displays the accessibility report for a processed PDF.
    """
    log.debug(f'starting view_report() for pk={pk}')
    doc = get_object_or_404(PDFDocument, pk=pk)

    ## TODO: Implement full report display logic
    ## For now, just show basic document info and status

    return render(
        request,
        'pdf_checker_app/report.html',
        {
            'document': doc,
        },
    )
