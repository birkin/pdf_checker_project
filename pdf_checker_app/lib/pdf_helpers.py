"""
Helper functions for PDF processing.
"""

import hashlib
import logging
import subprocess
from pathlib import Path

from django.conf import settings as project_settings
from django.core.files.uploadedfile import UploadedFile

log = logging.getLogger(__name__)


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


def save_temp_file(file: UploadedFile, checksum: str) -> Path:
    """
    Saves uploaded file to temporary storage.
    """
    temp_dir = Path(project_settings.BASE_DIR) / 'tmp' / 'uploads'
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f'{checksum}.pdf'

    with open(temp_path, 'wb') as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    return temp_path


def run_verapdf(pdf_path: Path, verapdf_cli_path: Path) -> dict[str, str]:
    """
    Runs veraPDF on a temporary file and returns the raw-json-output.
    Called by views.upload_pdf().

    Command flags:
    -f ua1 (PDF/UA-1 validation profile)
    --maxfailuresdisplayed 999999 (show all failures)
    --format json (output format)
    --success (include success messages) -- disabled to reduce the size of the output
    str(pdf_path) (path to pdf)

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
    completed_process = subprocess.run(
        command,
        cwd='.',
        capture_output=True,
        text=True,
    )
    output = str(completed_process.stdout)
    log.debug(f'output, ``{output}``')
    return output
