import uuid

from django.db import models


class PDFDocument(models.Model):
    """
    Stores uploaded PDF document metadata and Shibboleth user info.
    """

    ## Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ## File identification
    original_filename = models.CharField(max_length=255)
    file_checksum = models.CharField(max_length=64, unique=True, db_index=True)  # SHA-256
    file_size = models.BigIntegerField()  # bytes

    ## Shibboleth user information
    user_first_name = models.CharField(max_length=100, blank=True)
    user_last_name = models.CharField(max_length=100, blank=True)
    user_email = models.EmailField(blank=True)
    user_groups = models.JSONField(default=list, blank=True)  # List of groups

    ## Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)

    ## Status tracking
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
    )
    processing_error = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['file_checksum']),
            models.Index(fields=['-uploaded_at']),
        ]


class VeraPDFResult(models.Model):
    """
    Stores veraPDF analysis results.
    """

    ## Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ## Relationship
    pdf_document = models.OneToOneField(PDFDocument, on_delete=models.CASCADE, related_name='verapdf_result')

    ## veraPDF output
    raw_json = models.JSONField()  # Complete veraPDF JSON output

    ## Parsed results
    is_accessible = models.BooleanField()  # Pass/fail status
    validation_profile = models.CharField(max_length=50)  # e.g., "PDF/UA-1"

    ## Processing metadata
    analyzed_at = models.DateTimeField(auto_now_add=True)
    verapdf_version = models.CharField(max_length=20)

    ## Summary data
    total_checks = models.IntegerField(default=0)
    failed_checks = models.IntegerField(default=0)
    passed_checks = models.IntegerField(default=0)


class OpenRouterSummary(models.Model):
    """
    Stores OpenRouter LLM summary results for a PDF document.
    """

    ## Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ## Relationship
    pdf_document = models.OneToOneField(
        PDFDocument,
        on_delete=models.CASCADE,
        related_name='openrouter_summary',
    )

    ## Persistence fields
    raw_response_json = models.JSONField(null=True, blank=True)
    summary_text = models.TextField(blank=True)

    ## Identity/metadata fields (from OpenRouter response)
    openrouter_response_id = models.CharField(max_length=128, blank=True)
    provider = models.CharField(max_length=64, blank=True)
    model = models.CharField(max_length=128, blank=True)
    finish_reason = models.CharField(max_length=32, blank=True)

    ## Status/error fields
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
    )
    error = models.TextField(blank=True, null=True)

    ## Datetime fields
    requested_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    openrouter_created_at = models.DateTimeField(null=True, blank=True)

    ## Usage/cost fields
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    total_tokens = models.IntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = 'OpenRouter Summary'
        verbose_name_plural = 'OpenRouter Summaries'
