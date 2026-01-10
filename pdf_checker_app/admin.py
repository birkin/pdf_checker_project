from django.contrib import admin

from pdf_checker_app.models import PDFDocument, VeraPDFResult


@admin.register(PDFDocument)
class PDFDocumentAdmin(admin.ModelAdmin):
    """
    Admin interface for PDFDocument model.
    """
    list_display = [
        'original_filename',
        'user_email',
        'file_size',
        'processing_status',
        'uploaded_at',
    ]
    list_filter = [
        'processing_status',
        'uploaded_at',
    ]
    search_fields = [
        'original_filename',
        'user_email',
        'user_first_name',
        'user_last_name',
        'file_checksum',
    ]
    readonly_fields = [
        'file_checksum',
        'file_size',
        'uploaded_at',
    ]
    fieldsets = [
        ('File Information', {
            'fields': ['original_filename', 'file_checksum', 'file_size']
        }),
        ('User Information', {
            'fields': ['user_first_name', 'user_last_name', 'user_email', 'user_groups']
        }),
        ('Status', {
            'fields': ['processing_status', 'processing_error', 'uploaded_at']
        }),
    ]


@admin.register(VeraPDFResult)
class VeraPDFResultAdmin(admin.ModelAdmin):
    """
    Admin interface for VeraPDFResult model.
    """
    list_display = [
        'pdf_document',
        'is_accessible',
        'validation_profile',
        'passed_checks',
        'failed_checks',
        'analyzed_at',
    ]
    list_filter = [
        'is_accessible',
        'validation_profile',
        'analyzed_at',
    ]
    search_fields = [
        'pdf_document__original_filename',
        'validation_profile',
    ]
    readonly_fields = [
        'pdf_document',
        'raw_json',
        'analyzed_at',
        'verapdf_version',
    ]
    fieldsets = [
        ('Document', {
            'fields': ['pdf_document']
        }),
        ('Analysis Results', {
            'fields': [
                'is_accessible',
                'validation_profile',
                'total_checks',
                'passed_checks',
                'failed_checks',
            ]
        }),
        ('Metadata', {
            'fields': ['analyzed_at', 'verapdf_version']
        }),
        ('Raw Data', {
            'fields': ['raw_json'],
            'classes': ['collapse'],
        }),
    ]
