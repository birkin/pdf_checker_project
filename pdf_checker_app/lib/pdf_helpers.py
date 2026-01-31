"""
Helper functions for PDF processing.

Called by:
    - pdf_checker_app.views.upload_pdf() (file operations, checksum generation)
    - pdf_checker_app.lib.sync_processing_helpers (synchronous veraPDF attempts)
    - scripts.process_verapdf_jobs (cron background veraPDF processing)
"""

import hashlib
import json
import logging
import subprocess
import uuid
from pathlib import Path

from django.conf import settings as project_settings
from django.core.files.uploadedfile import UploadedFile

from pdf_checker_app.models import VeraPDFResult

log = logging.getLogger(__name__)


class VeraPDFTimeoutError(Exception):
    """
    Raised when veraPDF execution exceeds the specified timeout.
    """

    pass


def get_shibboleth_user_info(request) -> dict[str, str | list[str]]:
    """
    Extracts Shibboleth user information from request headers.
    """
    ## These header names may vary depending on your Shibboleth configuration
    ## Adjust as needed based on your Shibboleth SP configuration
    return {
        'first_name': request.META.get('HTTP_SHIB_GIVEN_NAME', ''),
        'last_name': request.META.get('HTTP_SHIB_SN', ''),
        'email': request.META.get('HTTP_SHIB_MAIL', ''),
        'groups': request.META.get('HTTP_SHIB_GROUPS', '').split(';') if request.META.get('HTTP_SHIB_GROUPS') else [],
    }


def generate_checksum(file: UploadedFile) -> str:
    """
    Generates SHA-256 checksum for uploaded file.
    """
    sha256_hash = hashlib.sha256()
    for chunk in file.chunks():
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def save_pdf_file(file: UploadedFile, checksum: str) -> Path:
    """
    Saves uploaded file to temporary storage.
    Called by:
        - pdf_checker_app.views.upload_pdf()
    """
    upload_dir_path = Path(project_settings.PDF_UPLOAD_PATH)
    absolute_upload_dir_path = upload_dir_path.resolve()
    absolute_upload_dir_path.mkdir(parents=True, exist_ok=True)
    upload_pdf_path = absolute_upload_dir_path / f'{checksum}.pdf'

    with open(upload_pdf_path, 'wb') as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    return upload_pdf_path


# def save_temp_file(file: UploadedFile, checksum: str) -> Path:
#     """
#     Saves uploaded file to temporary storage.
#     """
#     temp_dir = Path(project_settings.PDF_UPLOAD_PATH).expanduser()
#     if not temp_dir.is_absolute():
#         temp_dir = Path(project_settings.BASE_DIR) / temp_dir
#     temp_dir.mkdir(parents=True, exist_ok=True)
#     temp_path = temp_dir / f'{checksum}.pdf'

#     with open(temp_path, 'wb') as dest:
#         for chunk in file.chunks():
#             dest.write(chunk)

#     return temp_path


def run_verapdf(pdf_path: Path, verapdf_cli_path: Path, timeout_seconds: float | None = None) -> str:
    """
    Runs veraPDF on a temporary file and returns the raw-json-output.
    Called by:
        - pdf_checker_app.lib.sync_processing_helpers.attempt_verapdf_sync()
        - scripts.process_verapdf_jobs.process_single_job()

    Command flags:
    -f ua1 (PDF/UA-1 validation profile)
    --maxfailuresdisplayed 999999 (show all failures)
    --format json (output format)
    --success (include success messages) -- disabled to reduce the size of the output
    str(pdf_path) (path to pdf)

    Raises:
        VeraPDFTimeoutError: If execution exceeds timeout_seconds.
    """
    ## build command ------------------------------------------------
    command: list[str] = [
        str(verapdf_cli_path),
        '-f',
        'ua1',
        '--maxfailuresdisplayed',
        '999999',
        '--format',
        'json',
        # '--success',  ## removing this significantly reduces the output
        str(pdf_path),
    ]
    ## run command --------------------------------------------------
    try:
        completed_process = subprocess.run(
            command,
            cwd='.',
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        output = str(completed_process.stdout)
        log.debug(f'output, ``{output}``')
        return output
    except subprocess.TimeoutExpired as e:
        log.warning(f'veraPDF timed out after {timeout_seconds} seconds for {pdf_path}')
        raise VeraPDFTimeoutError(f'veraPDF execution exceeded {timeout_seconds} seconds') from e


def parse_verapdf_output(raw_output: str) -> dict[str, object]:
    """
    Parses the raw veraPDF JSON output into a Python dictionary.

    """
    log.debug('starting parse_verapdf_output()')
    parsed_output = json.loads(raw_output)
    if not isinstance(parsed_output, dict):
        raise ValueError('veraPDF output is not a JSON object.')
    overwrite_verapdf_job_item_names(parsed_output)
    return parsed_output


def get_verapdf_compliant(raw_json: dict[str, object]) -> bool | None:
    """
    Extracts the compliance boolean from veraPDF JSON output.

    Called by:
        - get_accessibility_assessment()
    """
    log.debug('starting get_verapdf_compliant()')
    result: bool | None = None
    report_obj: object | None = raw_json.get('report')
    report: dict[str, object]
    if isinstance(report_obj, dict):
        report = report_obj
    else:
        report = raw_json

    jobs_obj: object | None = report.get('jobs')
    if isinstance(jobs_obj, list) and jobs_obj:
        jobs: list[object] = jobs_obj

        job0_obj: object = jobs[0]
        if isinstance(job0_obj, dict):
            job0: dict[str, object] = job0_obj

            validation_result_obj: object | None = job0.get('validationResult')
            if isinstance(validation_result_obj, list) and validation_result_obj:
                validation_result: list[object] = validation_result_obj

                validation_result0_obj: object = validation_result[0]
                if isinstance(validation_result0_obj, dict):
                    validation_result0: dict[str, object] = validation_result0_obj

                    compliant: object | None = validation_result0.get('compliant')
                    if isinstance(compliant, bool):
                        result = compliant
    log.debug(f'result: ``{result}``')
    return result


def get_accessibility_assessment(raw_json: dict[str, object]) -> str | None:
    """
    Maps veraPDF compliance to an accessibility assessment label.

    Called by:
        - status_fragment()
        - view_report()
    """
    result: str | None = None
    compliant: bool | None = get_verapdf_compliant(raw_json)
    if compliant is True:
        result = 'accessible'
    elif compliant is False:
        result = 'not-accessible'
    return result


def overwrite_verapdf_job_item_names(raw_json: dict[str, object]) -> None:
    """
    Overwrites the input-file path stored by veraPDF in jobs[].itemDetails.name.

    Called by:
        - parse_verapdf_output()
    """
    report_obj: object | None = raw_json.get('report')
    report: dict[str, object]
    if isinstance(report_obj, dict):
        report = report_obj
    else:
        report = raw_json

    jobs = report.get('jobs')
    if not isinstance(jobs, list):
        return

    for job in jobs:
        if not isinstance(job, dict):
            continue

        item_details = job.get('itemDetails')
        if not isinstance(item_details, dict):
            continue

        name = item_details.get('name')
        if not isinstance(name, str):
            continue

        new_name = f'/path/to/pdf_uploads/{Path(name).name}'
        log.debug(f'overwriting veraPDF item name from ``{name}`` to ``{new_name}``')
        item_details['name'] = new_name


def save_verapdf_result(document_id: uuid.UUID, raw_json: dict[str, object]) -> VeraPDFResult:
    """
    Persists raw veraPDF JSON output for a document.
    """
    compliant = get_verapdf_compliant(raw_json)
    is_accessible = compliant if compliant is not None else False
    result, created = VeraPDFResult.objects.get_or_create(
        pdf_document_id=document_id,
        defaults={
            'raw_json': raw_json,
            'is_accessible': is_accessible,
            'validation_profile': 'PDF/UA-1',
            'verapdf_version': 'unknown',
        },
    )
    if not created:  # exists; will overwrite
        result.raw_json = raw_json
        result.is_accessible = is_accessible
        result.save(update_fields=['raw_json', 'is_accessible'])
    return result
