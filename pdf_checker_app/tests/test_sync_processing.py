"""
Tests for synchronous PDF processing with timeout fallback.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
from django.test import TestCase

from pdf_checker_app.lib.pdf_helpers import VeraPDFTimeoutError
from pdf_checker_app.lib.sync_processing_helpers import (
    attempt_openrouter_sync,
    attempt_synchronous_processing,
    attempt_verapdf_sync,
)
from pdf_checker_app.models import OpenRouterSummary, PDFDocument, VeraPDFResult

log = logging.getLogger(__name__)


class SyncVeraPDFProcessingTest(TestCase):
    """
    Checks synchronous veraPDF processing with timeout handling.
    """

    def setUp(self) -> None:
        """
        Creates a test document.
        """
        self.doc = PDFDocument.objects.create(
            original_filename='test.pdf',
            file_checksum='abc123',
            file_size=1024,
            processing_status='pending',
        )
        self.pdf_path = Path('/tmp/test.pdf')

    def test_verapdf_sync_success(self) -> None:
        """
        Checks that successful veraPDF updates document to 'completed'.
        """
        mock_output = '{"jobs": []}'
        mock_parsed = {'jobs': []}

        with patch('pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.run_verapdf', return_value=mock_output):
            with patch(
                'pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.parse_verapdf_output', return_value=mock_parsed
            ):
                with patch('pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.save_verapdf_result'):
                    result = attempt_verapdf_sync(self.doc, self.pdf_path)

        self.assertTrue(result)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, 'completed')
        self.assertIsNone(self.doc.processing_error)

    def test_verapdf_sync_timeout_fallback(self) -> None:
        """
        Checks that veraPDF timeout sets status to 'pending' for cron pickup.
        """
        with patch(
            'pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.run_verapdf',
            side_effect=VeraPDFTimeoutError('timeout'),
        ):
            result = attempt_verapdf_sync(self.doc, self.pdf_path)

        self.assertFalse(result)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, 'pending')
        self.assertIsNone(self.doc.processing_started_at)

    def test_verapdf_sync_error_marks_failed(self) -> None:
        """
        Checks that non-timeout errors mark document as 'failed'.
        """
        with patch(
            'pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.run_verapdf', side_effect=Exception('parse error')
        ):
            result = attempt_verapdf_sync(self.doc, self.pdf_path)

        self.assertFalse(result)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, 'failed')
        self.assertIn('parse error', self.doc.processing_error)


class SyncOpenRouterProcessingTest(TestCase):
    """
    Checks synchronous OpenRouter processing with timeout handling.
    """

    def setUp(self) -> None:
        """
        Creates a test document with veraPDF result.
        """
        self.doc = PDFDocument.objects.create(
            original_filename='test.pdf',
            file_checksum='abc123',
            file_size=1024,
            processing_status='completed',
        )
        self.verapdf_result = VeraPDFResult.objects.create(
            pdf_document=self.doc,
            raw_json={'jobs': []},
            is_accessible=True,
            validation_profile='PDF/UA-1',
            verapdf_version='1.0',
        )

    def test_openrouter_sync_success(self) -> None:
        """
        Checks that successful OpenRouter updates summary to 'completed'.
        """
        mock_response = {
            'id': 'test-id',
            'provider': 'test-provider',
            'model': 'test-model',
            'choices': [{'message': {'content': 'Test summary'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30},
            'created': 1234567890,
        }
        mock_parsed = {
            'summary_text': 'Test summary',
            'openrouter_response_id': 'test-id',
            'provider': 'test-provider',
            'model': 'test-model',
            'finish_reason': 'stop',
            'openrouter_created_at': None,
            'prompt_tokens': 10,
            'completion_tokens': 20,
            'total_tokens': 30,
        }

        with patch('pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value='test-key'):
            with patch(
                'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                return_value=['test-model'],
            ):
                with patch(
                    'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.filter_down_failure_checks',
                    return_value={},
                ):
                    with patch(
                        'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.build_prompt',
                        return_value='test prompt',
                    ):
                        with patch(
                            'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.call_openrouter',
                            return_value=mock_response,
                        ):
                            with patch(
                                'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.parse_openrouter_response',
                                return_value=mock_parsed,
                            ):
                                with patch(
                                    'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.persist_openrouter_summary'
                                ):
                                    result = attempt_openrouter_sync(self.doc)

        self.assertTrue(result)

    def test_openrouter_sync_timeout_fallback(self) -> None:
        """
        Checks that OpenRouter timeout sets summary status to 'pending'.
        """
        with patch('pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value='test-key'):
            with patch(
                'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                return_value=['test-model'],
            ):
                with patch(
                    'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.filter_down_failure_checks',
                    return_value={},
                ):
                    with patch(
                        'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.build_prompt',
                        return_value='test prompt',
                    ):
                        with patch(
                            'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.call_openrouter',
                            side_effect=httpx.TimeoutException('timeout'),
                        ):
                            result = attempt_openrouter_sync(self.doc)

        self.assertFalse(result)
        summary = OpenRouterSummary.objects.get(pdf_document=self.doc)
        self.assertEqual(summary.status, 'pending')
        self.assertIn('timed out', summary.error)

    def test_openrouter_sync_error_marks_failed(self) -> None:
        """
        Checks that non-timeout errors mark summary as 'failed'.
        """
        with patch('pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value='test-key'):
            with patch(
                'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                return_value=['test-model'],
            ):
                with patch(
                    'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.filter_down_failure_checks',
                    return_value={},
                ):
                    with patch(
                        'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.build_prompt',
                        return_value='test prompt',
                    ):
                        with patch(
                            'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.call_openrouter',
                            side_effect=Exception('API error'),
                        ):
                            result = attempt_openrouter_sync(self.doc)

        self.assertFalse(result)
        summary = OpenRouterSummary.objects.get(pdf_document=self.doc)
        self.assertEqual(summary.status, 'failed')
        self.assertIn('API error', summary.error)

    def test_openrouter_skipped_without_credentials(self) -> None:
        """
        Checks that OpenRouter is skipped if credentials are missing.
        """
        with patch('pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value=''):
            with patch(
                'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                return_value=['test-model'],
            ):
                result = attempt_openrouter_sync(self.doc)

        self.assertFalse(result)


class CronSelectionLogicTest(TestCase):
    """
    Checks cron job selection logic with stuck processing recovery.
    """

    def test_find_pending_jobs_includes_pending(self) -> None:
        """
        Checks that pending documents are selected.
        """
        doc = PDFDocument.objects.create(
            original_filename='test.pdf',
            file_checksum='abc123',
            file_size=1024,
            processing_status='pending',
        )

        from scripts.process_verapdf_jobs import find_pending_jobs

        jobs = find_pending_jobs(batch_size=10)
        self.assertIn(doc, jobs)

    def test_find_pending_jobs_skips_fresh_processing(self) -> None:
        """
        Checks that recently started processing jobs are skipped.
        """
        doc = PDFDocument.objects.create(
            original_filename='test.pdf',
            file_checksum='abc123',
            file_size=1024,
            processing_status='processing',
            processing_started_at=datetime.now(),
        )

        from scripts.process_verapdf_jobs import find_pending_jobs

        jobs = find_pending_jobs(batch_size=10)
        self.assertNotIn(doc, jobs)

    def test_find_pending_jobs_includes_stuck_processing(self) -> None:
        """
        Checks that old processing jobs are selected for recovery.
        """
        stuck_time = datetime.now() - timedelta(minutes=20)
        doc = PDFDocument.objects.create(
            original_filename='test.pdf',
            file_checksum='abc123',
            file_size=1024,
            processing_status='processing',
            processing_started_at=stuck_time,
        )

        from scripts.process_verapdf_jobs import find_pending_jobs

        jobs = find_pending_jobs(batch_size=10)
        self.assertIn(doc, jobs)


class FullSyncProcessingTest(TestCase):
    """
    Checks full synchronous processing orchestration.
    """

    def setUp(self) -> None:
        """
        Creates a test document.
        """
        self.doc = PDFDocument.objects.create(
            original_filename='test.pdf',
            file_checksum='abc123',
            file_size=1024,
            processing_status='pending',
        )
        self.pdf_path = Path('/tmp/test.pdf')

    def test_full_sync_success_path(self) -> None:
        """
        Checks that successful sync processing completes both veraPDF and OpenRouter.
        """
        mock_verapdf_output = '{"jobs": []}'
        mock_verapdf_parsed = {'jobs': []}
        mock_openrouter_response = {
            'id': 'test-id',
            'provider': 'test-provider',
            'model': 'test-model',
            'choices': [{'message': {'content': 'Test summary'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30},
            'created': 1234567890,
        }
        mock_openrouter_parsed = {
            'summary_text': 'Test summary',
            'openrouter_response_id': 'test-id',
            'provider': 'test-provider',
            'model': 'test-model',
            'finish_reason': 'stop',
            'openrouter_created_at': None,
            'prompt_tokens': 10,
            'completion_tokens': 20,
            'total_tokens': 30,
        }

        with patch('pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.run_verapdf', return_value=mock_verapdf_output):
            with patch(
                'pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.parse_verapdf_output',
                return_value=mock_verapdf_parsed,
            ):
                with patch('pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.save_verapdf_result'):
                    with patch(
                        'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value='test-key'
                    ):
                        with patch(
                            'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                            return_value=['test-model'],
                        ):
                            with patch(
                                'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.filter_down_failure_checks',
                                return_value={},
                            ):
                                with patch(
                                    'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.build_prompt',
                                    return_value='test prompt',
                                ):
                                    with patch(
                                        'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.call_openrouter',
                                        return_value=mock_openrouter_response,
                                    ):
                                        with patch(
                                            'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.parse_openrouter_response',
                                            return_value=mock_openrouter_parsed,
                                        ):
                                            with patch(
                                                'pdf_checker_app.lib.sync_processing_helpers.openrouter_helpers.persist_openrouter_summary'
                                            ):
                                                attempt_synchronous_processing(self.doc, self.pdf_path)

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, 'completed')
        self.assertIsNotNone(self.doc.processing_started_at)

    def test_verapdf_timeout_stops_openrouter_attempt(self) -> None:
        """
        Checks that veraPDF timeout prevents OpenRouter from being attempted.
        """
        with patch(
            'pdf_checker_app.lib.sync_processing_helpers.pdf_helpers.run_verapdf', side_effect=VeraPDFTimeoutError('timeout')
        ):
            attempt_synchronous_processing(self.doc, self.pdf_path)

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, 'pending')
        self.assertFalse(OpenRouterSummary.objects.filter(pdf_document=self.doc).exists())
