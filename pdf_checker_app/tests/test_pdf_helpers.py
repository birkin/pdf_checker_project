import logging
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase as TestCase
from django.test.utils import override_settings

from pdf_checker_app.lib import pdf_helpers

log = logging.getLogger(__name__)
TestCase.maxDiff = 1000


class PDFHelperSaveTempFileTest(TestCase):
    """
    Checks save_temp_file storage.
    """

    def test_save_temp_file_uses_pdf_upload_path(self) -> None:
        """
        Checks that save_temp_file writes into PDF_UPLOAD_PATH.
        """
        content: bytes = b'%PDF-1.4 test content'
        upload = SimpleUploadedFile('test.pdf', content, content_type='application/pdf')
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(PDF_UPLOAD_PATH=temp_dir):
                saved_path = pdf_helpers.save_pdf_file(upload, 'test_checksum_123')
                log.debug(f'saved_path, ``{saved_path}``')
                self.assertEqual(Path(temp_dir), saved_path.parent)
                self.assertTrue(saved_path.exists())
                self.assertEqual(content, saved_path.read_bytes())
