from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

try:
    import magic
    MAGIC_AVAILABLE = True
except (ImportError, OSError):
    MAGIC_AVAILABLE = False


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
        
        ## Check file size (50MB limit)
        if file.size > 50 * 1024 * 1024:
            raise ValidationError('File size exceeds 50MB limit.')
        
        ## Check file extension
        if not file.name.lower().endswith('.pdf'):
            raise ValidationError('File must have a .pdf extension.')
        
        ## Check PDF magic bytes (PDF files start with %PDF-)
        file.seek(0)
        header = file.read(5)
        file.seek(0)  # Reset file pointer
        
        if header != b'%PDF-':
            raise ValidationError('File must be a valid PDF document.')
        
        ## If python-magic is available, use it for additional validation
        if MAGIC_AVAILABLE:
            try:
                file_type = magic.from_buffer(file.read(2048), mime=True)
                file.seek(0)  # Reset file pointer
                
                if file_type != 'application/pdf':
                    raise ValidationError('File must be a PDF document.')
            except Exception:
                ## If magic fails, rely on the header check above
                pass
        
        return file
