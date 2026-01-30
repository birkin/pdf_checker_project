"""
Tests for htmx polling fragment endpoints.
"""

import logging
import uuid

from django.test import TestCase
from django.urls import reverse

from pdf_checker_app.models import OpenRouterSummary, PDFDocument, VeraPDFResult

log = logging.getLogger(__name__)
TestCase.maxDiff = 1000


class StatusFragmentTest(TestCase):
    """
    Checks status fragment endpoint behavior.
    """

    def setUp(self):
        """
        Sets up test data.
        """
        self.test_uuid = uuid.uuid4()
        self.document = PDFDocument.objects.create(
            id=self.test_uuid,
            original_filename='test.pdf',
            file_checksum='test_checksum_status',
            file_size=1024,
            processing_status='pending',
        )

    def test_status_fragment_pending(self):
        """
        Checks that status fragment returns polling attributes for pending status.
        """
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'hx-get')
        self.assertContains(response, 'hx-trigger')
        self.assertContains(response, 'queued for processing')

    def test_status_fragment_processing(self):
        """
        Checks that status fragment returns polling attributes for processing status.
        """
        self.document.processing_status = 'processing'
        self.document.save()
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'hx-get')
        self.assertContains(response, 'currently being processed')

    def test_status_fragment_completed(self):
        """
        Checks that status fragment stops polling for completed status.
        """
        self.document.processing_status = 'completed'
        self.document.save()
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Processing complete')
        ## Should trigger verapdf fragment load
        self.assertContains(response, 'verapdf.fragment')

    def test_status_fragment_failed(self):
        """
        Checks that status fragment stops polling for failed status.
        """
        self.document.processing_status = 'failed'
        self.document.save()
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Processing failed')
        ## Should not have polling attributes
        self.assertNotContains(response, 'hx-trigger="every')

    def test_status_fragment_invalid_uuid(self):
        """
        Checks that status fragment returns 404 for invalid UUID.
        """
        invalid_uuid = uuid.uuid4()
        url = reverse('status_fragment_url', kwargs={'pk': invalid_uuid})
        response = self.client.get(url)
        self.assertEqual(404, response.status_code)

    def test_status_fragment_cache_control(self):
        """
        Checks that status fragment sets Cache-Control header.
        """
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual('no-store', response['Cache-Control'])


class VerapdfFragmentTest(TestCase):
    """
    Checks veraPDF fragment endpoint behavior.
    """

    def setUp(self):
        """
        Sets up test data.
        """
        self.test_uuid = uuid.uuid4()
        self.document = PDFDocument.objects.create(
            id=self.test_uuid,
            original_filename='test.pdf',
            file_checksum='test_checksum_verapdf',
            file_size=1024,
            processing_status='completed',
        )

    def test_verapdf_fragment_no_result(self):
        """
        Checks that verapdf fragment handles missing result gracefully.
        """
        url = reverse('verapdf_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'No veraPDF results available')

    def test_verapdf_fragment_with_result(self):
        """
        Checks that verapdf fragment returns JSON when result exists.
        """
        VeraPDFResult.objects.create(
            pdf_document=self.document,
            raw_json={'test': 'data'},
            is_accessible=True,
            validation_profile='PDF/UA-1',
            verapdf_version='1.0',
        )
        url = reverse('verapdf_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'veraPDF Response')
        self.assertContains(response, 'test')

    def test_verapdf_fragment_pending_status(self):
        """
        Checks that verapdf fragment returns empty container for pending status.
        """
        self.document.processing_status = 'pending'
        self.document.save()
        url = reverse('verapdf_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        ## Should not contain JSON content
        self.assertNotContains(response, 'Raw veraPDF JSON')

    def test_verapdf_fragment_cache_control(self):
        """
        Checks that verapdf fragment sets Cache-Control header.
        """
        url = reverse('verapdf_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual('no-store', response['Cache-Control'])


class SummaryFragmentTest(TestCase):
    """
    Checks summary fragment endpoint behavior.
    """

    def setUp(self):
        """
        Sets up test data.
        """
        self.test_uuid = uuid.uuid4()
        self.document = PDFDocument.objects.create(
            id=self.test_uuid,
            original_filename='test.pdf',
            file_checksum='test_checksum_summary',
            file_size=1024,
            processing_status='completed',
        )

    def test_summary_fragment_no_summary(self):
        """
        Checks that summary fragment handles missing summary gracefully.
        """
        url = reverse('summary_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Suggestions coming soon')

    def test_summary_fragment_pending(self):
        """
        Checks that summary fragment shows pending state with polling.
        """
        OpenRouterSummary.objects.create(
            pdf_document=self.document,
            status='pending',
        )
        url = reverse('summary_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'hx-get')
        self.assertContains(response, 'queued for generation')

    def test_summary_fragment_processing(self):
        """
        Checks that summary fragment shows processing state with polling.
        """
        OpenRouterSummary.objects.create(
            pdf_document=self.document,
            status='processing',
        )
        url = reverse('summary_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'hx-get')
        self.assertContains(response, 'Generating suggestions')

    def test_summary_fragment_completed(self):
        """
        Checks that summary fragment shows completed summary.
        """
        OpenRouterSummary.objects.create(
            pdf_document=self.document,
            status='completed',
            summary_text='This is a test summary.',
            model='gpt-4',
        )
        url = reverse('summary_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'This is a test summary')
        self.assertContains(response, 'gpt-4')
        ## Should not have polling attributes
        self.assertNotContains(response, 'hx-trigger="every')

    def test_summary_fragment_failed(self):
        """
        Checks that summary fragment shows failed state.
        """
        OpenRouterSummary.objects.create(
            pdf_document=self.document,
            status='failed',
            error='API error',
        )
        url = reverse('summary_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Suggestion generation failed')

    def test_summary_fragment_cache_control(self):
        """
        Checks that summary fragment sets Cache-Control header.
        """
        url = reverse('summary_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual('no-store', response['Cache-Control'])
