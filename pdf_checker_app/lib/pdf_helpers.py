"""
Helper functions for PDF processing.
"""

import hashlib
import logging
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
