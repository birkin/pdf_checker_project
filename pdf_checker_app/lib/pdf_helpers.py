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
    Called by views.upload_pdf().
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
    Called by views.upload_pdf().

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
    parsed_output = json.loads(raw_output)
    if not isinstance(parsed_output, dict):
        raise ValueError('veraPDF output is not a JSON object.')
    overwrite_verapdf_job_item_names(parsed_output)
    return parsed_output


def overwrite_verapdf_job_item_names(raw_json: dict[str, object]) -> None:
    jobs = raw_json.get('jobs')
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

        item_details['name'] = f'/path/to/pdf_uploads/{Path(name).name}'


def save_verapdf_result(document_id: uuid.UUID, raw_json: dict[str, object]) -> VeraPDFResult:
    """
    Persists raw veraPDF JSON output for a document.
    """
    result, created = VeraPDFResult.objects.get_or_create(
        pdf_document_id=document_id,
        defaults={
            'raw_json': raw_json,
            'is_accessible': False,
            'validation_profile': 'PDF/UA-1',
            'verapdf_version': 'unknown',
        },
    )
    if not created:  # exists; will overwrite
        result.raw_json = raw_json
        result.save(update_fields=['raw_json'])
    return result
