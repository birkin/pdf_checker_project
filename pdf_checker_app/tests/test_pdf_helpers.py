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
                self.assertEqual(Path(temp_dir).resolve(), saved_path.parent)
                self.assertTrue(saved_path.exists())
                self.assertEqual(content, saved_path.read_bytes())


class PDFHelperParseVeraPDFOutputTest(TestCase):
    def test_parse_verapdf_output_overwrites_job_item_name(self) -> None:
        """
        Checks that parse_verapdf_output() overwrites jobs[0].itemDetails.name.
        """
        raw_output = (
            '{'
            '  "jobs": ['
            '    {'
            '      "itemDetails": {'
            '        "name": "/Users/birkin/Documents/Brown_Library/djangoProjects/pdf_checker_stuff/pdf_uploads/test.pdf",'
            '        "size": 123'
            '      }'
            '    }'
            '  ]'
            '}'
        )

        parsed = pdf_helpers.parse_verapdf_output(raw_output)
        jobs = parsed.get('jobs')
        self.assertIsInstance(jobs, list)
        first_job = jobs[0]
        self.assertIsInstance(first_job, dict)
        item_details = first_job.get('itemDetails')
        self.assertIsInstance(item_details, dict)
        self.assertEqual(item_details.get('name'), '/path/to/pdf_uploads/test.pdf')
