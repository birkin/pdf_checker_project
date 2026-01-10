# PDF Upload Form Implementation Plan

- review `pdf_checker_project/PLAN__high-level-implementation.md` for background

- review `pdf_checker_project/AGENTS.md` for coding directives.

## Overview

This document outlines the implementation plan for the initial PDF upload form feature, focusing on a simple web interface (no API) that performs basic PDF accessibility checking using veraPDF.

## Scope

### What's Included (Initial Implementation)
- Web form for PDF upload
- PDF file validation
- Checksum generation and storage
- veraPDF accessibility checking
- JSON result storage in SQLite
- Simple pass/fail report display
- List of accessibility issues found

### What's NOT Included (Future Iterations)
- API endpoints
- LLM processing
- Queue/worker architecture
- WebSockets or real-time updates
- Batch processing
- Advanced caching strategies

## Technical Components

### 1. Database Models

#### PDFDocument Model
```python
# pdf_checker_app/models.py
class PDFDocument(models.Model):
    """
    Stores uploaded PDF document metadata and Shibboleth user info.
    """
    # File identification
    original_filename = models.CharField(max_length=255)
    file_checksum = models.CharField(max_length=64, unique=True, db_index=True)  # SHA-256
    file_size = models.BigIntegerField()  # bytes
    
    # Shibboleth user information
    user_first_name = models.CharField(max_length=100, blank=True)
    user_last_name = models.CharField(max_length=100, blank=True)
    user_email = models.EmailField(blank=True)
    user_groups = models.JSONField(default=list, blank=True)  # List of groups
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Status tracking
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    processing_error = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['file_checksum']),
            models.Index(fields=['-uploaded_at']),
        ]
```

#### VeraPDFResult Model
```python
class VeraPDFResult(models.Model):
    """
    Stores veraPDF analysis results.
    """
    # Relationship
    pdf_document = models.OneToOneField(
        PDFDocument, 
        on_delete=models.CASCADE,
        related_name='verapdf_result'
    )
    
    # veraPDF output
    raw_json = models.JSONField()  # Complete veraPDF JSON output
    
    # Parsed results
    is_accessible = models.BooleanField()  # Pass/fail status
    validation_profile = models.CharField(max_length=50)  # e.g., "PDF/UA-1"
    
    # Processing metadata
    analyzed_at = models.DateTimeField(auto_now_add=True)
    verapdf_version = models.CharField(max_length=20)
    
    # Summary data
    total_checks = models.IntegerField(default=0)
    failed_checks = models.IntegerField(default=0)
    passed_checks = models.IntegerField(default=0)
```

### 2. Forms

#### PDF Upload Form
```python
# pdf_checker_app/forms.py
from django import forms
from django.core.exceptions import ValidationError
import magic

class PDFUploadForm(forms.Form):
    """
    Form for uploading PDF files.
    """
    pdf_file = forms.FileField(
        label='Select PDF file',
        help_text='Maximum file size: 50MB',
        widget=forms.FileInput(attrs={
            'accept': '.pdf,application/pdf',
            'class': 'form-control',
        })
    )
    
    def clean_pdf_file(self) -> UploadedFile:
        """
        Validates that the uploaded file is a PDF.
        """
        file = self.cleaned_data['pdf_file']
        
        # Check file size (50MB limit)
        if file.size > 50 * 1024 * 1024:
            raise ValidationError('File size exceeds 50MB limit.')
        
        # Check MIME type using python-magic
        file_type = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)  # Reset file pointer
        
        if file_type != 'application/pdf':
            raise ValidationError('File must be a PDF document.')
        
        return file
```

### 3. Views

#### Upload View
```python
# pdf_checker_app/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
import hashlib
from .forms import PDFUploadForm
from .models import PDFDocument, VeraPDFResult

def get_shibboleth_user_info(request) -> dict:
    """
    Extracts Shibboleth user information from request headers.
    """
    # These header names may vary depending on your Shibboleth configuration
    # Adjust as needed based on your Shibboleth SP configuration
    return {
        'first_name': request.META.get('HTTP_SHIB_GIVEN_NAME', ''),
        'last_name': request.META.get('HTTP_SHIB_SN', ''),
        'email': request.META.get('HTTP_SHIB_MAIL', ''),
        'groups': request.META.get('HTTP_SHIB_GROUPS', '').split(';') if request.META.get('HTTP_SHIB_GROUPS') else [],
    }

def upload_pdf(request):
    """
    Handles PDF upload and initiates processing.
    """
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            
            # Get Shibboleth user info
            user_info = get_shibboleth_user_info(request)
            
            # Generate checksum
            checksum = generate_checksum(pdf_file)
            
            # Check if already processed
            existing_doc = PDFDocument.objects.filter(
                file_checksum=checksum
            ).first()
            
            if existing_doc and existing_doc.processing_status == 'completed':
                messages.info(request, 'This PDF has already been processed.')
                return redirect('pdf_checker_app:report', pk=existing_doc.pk)
            
            # Create new document record with Shibboleth user info
            if not existing_doc:
                doc = PDFDocument.objects.create(
                    original_filename=pdf_file.name,
                    file_checksum=checksum,
                    file_size=pdf_file.size,
                    user_first_name=user_info['first_name'],
                    user_last_name=user_info['last_name'],
                    user_email=user_info['email'],
                    user_groups=user_info['groups'],
                    processing_status='pending'
                )
            else:
                doc = existing_doc
            
            # Save temporary file for processing
            temp_path = save_temp_file(pdf_file, checksum)
            
            # TODO: Process with veraPDF (will be implemented separately)
            # For now, just mark as pending and redirect
            messages.success(request, 'PDF uploaded successfully and queued for processing.')
            return redirect('pdf_checker_app:report', pk=doc.pk)
    else:
        form = PDFUploadForm()
    
    return render(request, 'pdf_checker_app/upload.html', {
        'form': form
    })

def generate_checksum(file) -> str:
    """
    Generates SHA-256 checksum for uploaded file.
    """
    sha256_hash = hashlib.sha256()
    for chunk in file.chunks():
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()
```

#### Report View (Stub)
```python
def view_report(request, pk: int):
    """
    Displays the accessibility report for a processed PDF.
    (STUB - to be fully implemented later)
    """
    doc = get_object_or_404(PDFDocument, pk=pk)
    
    # TODO: Implement full report display logic
    # For now, just show basic document info and status
    
    return render(request, 'pdf_checker_app/report.html', {
        'document': doc,
    })
```

### 4. veraPDF Integration (Future Implementation)

*Note: The VeraPDF Processor class will be implemented in a later phase. For the initial upload form implementation, we'll focus on capturing the file and storing it in the database with user information.*

### 5. Templates

#### Base Template
```html
<!-- pdf_checker_app/templates/pdf_checker_app/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PDF Accessibility Checker{% endblock %}</title>
    <style>
        /* CSS-first approach with modern, clean design */
        :root {
            --color-primary: #2563eb;
            --color-success: #16a34a;
            --color-error: #dc2626;
            --color-warning: #d97706;
            --color-info: #0891b2;
            --color-bg: #f9fafb;
            --color-border: #e5e7eb;
        }
        
        body {
            font-family: system-ui, -apple-system, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background: var(--color-bg);
            margin: 0;
            padding: 0;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .card {
            background: white;
            border-radius: 8px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        /* Additional styles... */
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <div class="container">
        {% if messages %}
            <div class="messages">
                {% for message in messages %}
                    <div class="alert alert-{{ message.tags }}">
                        {{ message }}
                    </div>
                {% endfor %}
            </div>
        {% endif %}
        
        {% block content %}{% endblock %}
    </div>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

#### Upload Template
```html
<!-- pdf_checker_app/templates/pdf_checker_app/upload.html -->
{% extends "pdf_checker_app/base.html" %}

{% block title %}Upload PDF - PDF Accessibility Checker{% endblock %}

{% block content %}
<div class="card">
    <h1>PDF Accessibility Checker</h1>
    <p>Upload a PDF document to check its accessibility compliance using veraPDF.</p>
    
    <form method="post" enctype="multipart/form-data" id="upload-form">
        {% csrf_token %}
        
        <div class="form-group">
            {{ form.pdf_file.label_tag }}
            {{ form.pdf_file }}
            {% if form.pdf_file.help_text %}
                <small class="help-text">{{ form.pdf_file.help_text }}</small>
            {% endif %}
            {% if form.pdf_file.errors %}
                <div class="error">{{ form.pdf_file.errors }}</div>
            {% endif %}
        </div>
        
        <!-- Drag and drop area -->
        <div id="drop-zone" class="drop-zone">
            <p>Or drag and drop your PDF here</p>
        </div>
        
        <button type="submit" class="btn btn-primary">
            Check Accessibility
        </button>
    </form>
</div>

<script>
    // Simple drag-and-drop enhancement
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('id_pdf_file');
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            // Optional: auto-submit
            // document.getElementById('upload-form').submit();
        }
    });
</script>
{% endblock %}
```

#### Report Template (Stub)
```html
<!-- pdf_checker_app/templates/pdf_checker_app/report.html -->
{% extends "pdf_checker_app/base.html" %}

{% block title %}Report - {{ document.original_filename }}{% endblock %}

{% block content %}
<div class="card">
    <h1>PDF Processing Report</h1>
    
    <div class="document-info">
        <h2>Document Information</h2>
        <dl>
            <dt>File:</dt>
            <dd>{{ document.original_filename }}</dd>
            
            <dt>Uploaded by:</dt>
            <dd>{{ document.user_first_name }} {{ document.user_last_name }} ({{ document.user_email }})</dd>
            
            <dt>Uploaded:</dt>
            <dd>{{ document.uploaded_at|date:"Y-m-d H:i" }}</dd>
            
            <dt>Size:</dt>
            <dd>{{ document.file_size|filesizeformat }}</dd>
            
            <dt>Status:</dt>
            <dd>{{ document.get_processing_status_display }}</dd>
        </dl>
    </div>
    
    {% if document.processing_status == 'pending' %}
    <div class="status-pending">
        <p>This PDF is queued for processing. Please check back later.</p>
    </div>
    {% elif document.processing_status == 'processing' %}
    <div class="status-processing">
        <p>This PDF is currently being processed. Please check back shortly.</p>
    </div>
    {% elif document.processing_status == 'failed' %}
    <div class="status-failed">
        <p>Processing failed: {{ document.processing_error }}</p>
    </div>
    {% elif document.processing_status == 'completed' %}
    <div class="status-completed">
        <!-- TODO: Display actual veraPDF results once processing is implemented -->
        <p>Processing complete. Detailed results will be displayed here.</p>
    </div>
    {% endif %}
    
    <div class="actions">
        <a href="{% url 'pdf_checker_app:upload' %}" class="btn btn-secondary">
            Upload Another PDF
        </a>
    </div>
</div>
{% endblock %}
```

### 6. URL Configuration

```python
# pdf_checker_app/urls.py
from django.urls import path
from . import views

app_name = 'pdf_checker_app'

urlpatterns = [
    path('', views.upload_pdf, name='upload'),
    path('report/<int:pk>/', views.view_report, name='report'),
]
```

```python
# config/urls.py (addition)
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pdf_checker_app.urls')),
    # ... other patterns
]
```

### 7. Settings Configuration

```python
# config/settings.py additions

# veraPDF Configuration
VERAPDF_PATH = env('VERAPDF_PATH', default='/usr/local/bin/verapdf')
VERAPDF_PROFILE = env('VERAPDF_PROFILE', default='PDFUA_1_MACHINE')

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

# Temp file storage
TEMP_FILE_PATH = BASE_DIR / 'tmp' / 'uploads'
TEMP_FILE_PATH.mkdir(parents=True, exist_ok=True)
```

## Implementation Steps

### Phase 1: Foundation
1. Create database models
2. Run migrations
3. Create basic forms
4. Implement file upload view
5. Add URL patterns

### Phase 2: Processing
1. Implement checksum generation
2. Add veraPDF processor class
3. Integrate veraPDF with view
4. Parse veraPDF JSON output
5. Store results in database

### Phase 3: Reporting
1. Create report view
2. Design report template
3. Implement issue grouping
4. Add styling for pass/fail status

### Phase 4: Enhancement
1. Add drag-and-drop support
2. Improve error handling
3. Add duplicate detection
4. Implement temporary file cleanup

## Testing Strategy

### Unit Tests
```python
# tests/test_models.py
- Test PDFDocument model creation
- Test checksum uniqueness
- Test status transitions

# tests/test_forms.py
- Test PDF validation
- Test file size limits
- Test invalid file types

# tests/test_verapdf.py
- Test command execution
- Test JSON parsing
- Test error handling
- Mock veraPDF responses
```

### Integration Tests
```python
# tests/test_views.py
- Test complete upload flow
- Test duplicate file handling
- Test report generation
- Test error scenarios
```

## Dependencies to Add

```toml
# pyproject.toml additions
[project]
dependencies = [
    # ... existing dependencies
    "python-magic>=0.4.27",  # File type detection
]
```

## Environment Variables

```bash
# .env additions
VERAPDF_PATH=/usr/local/bin/verapdf
VERAPDF_PROFILE=PDFUA_1_MACHINE
```

## Future Enhancements

After this initial implementation is working:

1. **Async Processing**
   - Move to background processing with cronjob
   - Add processing queue table
   - Implement batch processor script

2. **Caching Improvements**
   - Add result caching by checksum
   - Implement cache expiry
   - Add cache statistics

3. **UI Enhancements**
   - Add progress indicators
   - Implement HTMX for dynamic updates
   - Add file preview
   - Export reports as PDF/CSV

4. **API Addition**
   - Add REST endpoints
   - Implement authentication
   - Add rate limiting

5. **LLM Integration**
   - Add LLM processing for human-readable reports
   - Implement prompt templates
   - Add model selection logic

## Notes

- The entire web form will be protected by Shibboleth authentication
- Shibboleth provides user information (first name, last name, email, groups) via headers
- No individual AccessibilityIssue records - all issue details remain in the raw JSON
- Report view and template are stubbed for initial implementation
- VeraPDF processor implementation deferred to focus on upload form first
- This plan follows the CSS-first approach with minimal JavaScript
- No WebSockets or real-time updates in initial version
- Synchronous processing initially (async via cronjob later)
- Using Django's built-in test framework
- Following project's coding standards from AGENTS.md

---
