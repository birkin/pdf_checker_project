# High-Level Implementation Plan for PDF Checker Project

## Overview

This document outlines the high-level implementation plan for the PDF Checker webapp, which provides both a web interface and API endpoints for checking PDF accessibility using veraPDF and generating human-readable reports via LLM processing.

## Current State Analysis

The project is a Django web application (v5.2) using Python 3.12 and `uv` for dependency management. The basic Django structure is in place with:
- `config/` directory containing Django settings and URLs
- `pdf_checker_app/` as the main application
- Basic views and templates
- Test infrastructure using Django's test framework
- CI/CD setup with GitHub Actions

## Functional Sections to Implement

### 1. URL Endpoints & Routing

**Purpose**: Define and implement all necessary URL patterns for both web interface and API access.

**Key Components**:
- Web interface endpoints:
  - Home/landing page with upload form
  - Upload handler endpoint
  - Results display page
  - Report download endpoint
- API endpoints:
  - PDF upload & analysis endpoint
  - Status check endpoint (for async processing)
  - Report retrieval endpoint
- Admin interface customizations

**Considerations**:
- RESTful API design patterns
- Authentication/authorization for API access
- Rate limiting for API endpoints
- CORS configuration for API access

### 2. File Upload & Management

**Purpose**: Handle PDF file uploads, validation, and temporary storage.

**Key Components**:
- Django forms for file upload
- File validation (PDF format, size limits)
- Temporary file storage management
- File cleanup mechanisms
- Progress indicators for large files

**Considerations**:
- Maximum file size configuration
- Secure file handling practices
- Asynchronous upload support for large files
- Multi-file batch processing for API

### 3. Database Models & Storage

**Purpose**: Define data models for storing PDF analysis results, reports, and metadata.

**Key Components**:
- PDFDocument model (file info, checksum, upload metadata)
- AnalysisResult model (veraPDF output, timestamps)
- ProcessedReport model (LLM-generated reports)
- APIRequest model (for tracking API usage)
- Cache/checksum lookup tables

**Considerations**:
- Efficient checksum indexing
- JSON field storage for veraPDF results
- Text field optimization for long reports
- Database migrations strategy
- Data retention policies

### 4. veraPDF Integration

**Purpose**: Integrate veraPDF tool for PDF accessibility checking.

**Key Components**:
- veraPDF installation/configuration management
- Command-line wrapper for veraPDF execution
- Result parser for veraPDF JSON/XML output
- Error handling for veraPDF failures
- Async processing queue for analysis

**Considerations**:
- veraPDF version management
- Profile selection (PDF/UA, WCAG, etc.)
- Performance optimization for large PDFs
- Containerization for veraPDF isolation
- Fallback mechanisms if veraPDF fails

### 5. Checksum & Caching System

**Purpose**: Implement efficient caching to avoid redundant processing.

**Key Components**:
- SHA-256 checksum generation for PDFs
- Cache key generation (checksum + analysis parameters)
- Cache lookup logic
- Cache invalidation strategies
- Storage optimization for cached results

**Considerations**:
- Cache expiration policies
- Storage limits and cleanup
- Cache warming strategies
- Distributed caching for scalability

### 6. LLM Integration & Report Generation

**Purpose**: Process veraPDF results through LLMs to generate human-readable reports.

**Key Components**:
- LLM provider abstraction layer
- Model configuration management
- Prompt engineering for report generation
- Context size handling for different models
- Response parsing and formatting
- Fallback model chain

**Considerations**:
- API key management (secure storage)
- Model selection logic (cost vs. quality)
- Token usage tracking and optimization
- Prompt template versioning
- Response caching
- Error handling for LLM failures
- Rate limiting and retry logic

### 7. Frontend User Interface

**Purpose**: Create an intuitive web interface for PDF upload and report viewing.

**Key Components**:
- Upload page with drag-and-drop support
- Progress indicators during processing
- Results display with formatted reports
- Report download options (PDF, HTML, JSON)
- History/previous reports view
- Responsive design for mobile access

**Considerations**:
- Modern, accessible UI design
- Real-time status updates (WebSockets/SSE)
- Client-side validation
- Browser compatibility
- Progressive enhancement

### 8. API Interface & Documentation

**Purpose**: Provide programmatic access to PDF checking functionality.

**Key Components**:
- RESTful API design
- Authentication system (API keys/tokens)
- Request/response serializers
- API documentation (OpenAPI/Swagger)
- Client libraries/examples
- Webhook support for async results 

**Considerations**:
- API versioning strategy
- Rate limiting per client
- Batch processing endpoints
- Response format options (JSON, XML)
- Error response standardization

### 9. Background Task Processing

**Purpose**: Handle asynchronous processing of PDF analysis and report generation.

**Key Components**:
Original plan:
- ~~Task queue setup (Celery or similar)~~
- ~~Worker configuration~~
- ~~Task status tracking~~
- Result storage and retrieval
- Task retry logic
- ~~Priority queue management~~

Developer-comment: 
- No, I don't want a queue/worker architecture for now. Initially, I'll use a cronjob calling a script (that will be part of this project) to see if the DB contains new things to process, and process a batch.

**Considerations**:
- ~~Scalability (multiple workers)~~
- ~~Task timeout handling~~
- Memory management for large PDFs
- ~~Dead letter queue for failed tasks~~

### 10. Monitoring & Logging

**Purpose**: Track system health, usage patterns, and debugging information.

**Key Components**:
- Structured logging setup
- Performance metrics collection
- Error tracking and alerting
- Usage analytics
- API request logging
- Cost tracking (for LLM usage)

**Considerations**:
- Log rotation and retention
- Privacy compliance (GDPR, etc.)
- Dashboard creation
- Alert thresholds
- Audit trail requirements

### 11. Testing Infrastructure

**Purpose**: Ensure reliability and maintainability through comprehensive testing.

**Key Components**:
- Unit tests for all components
- Integration tests for veraPDF and LLM
- API endpoint tests
- Frontend UI tests
- Load/performance tests
- Mock services for external dependencies

**Considerations**:
- Test data management
- CI/CD integration
- Code coverage targets
- Mock veraPDF responses
- Mock LLM responses

### 12. Deployment & Configuration

**Purpose**: Prepare the application for production deployment.

**Key Components**:
- Environment-specific settings
- Docker containerization
- Database migration strategy
- Static file serving
- HTTPS/SSL configuration
- Backup strategies

**Considerations**:
- Zero-downtime deployments
- Rollback procedures
- Secret management
- Auto-scaling configuration
- CDN integration for static files

## Implementation Priority

### Phase 1: Foundation (Core Functionality)
1. Database Models & Storage
2. File Upload & Management
3. URL Endpoints & Routing (basic)
4. veraPDF Integration

### Phase 2: Intelligence Layer
1. Checksum & Caching System
2. LLM Integration & Report Generation
3. Background Task Processing

### Phase 3: User Experience
1. Frontend User Interface
2. API Interface & Documentation
3. URL Endpoints & Routing (complete)

### Phase 4: Production Readiness
1. Testing Infrastructure
2. Monitoring & Logging
3. Deployment & Configuration

## Dependencies & Tools

### External Services
- veraPDF (command-line tool or API)
- LLM providers (OpenAI, Anthropic, local models)
- Cloud storage (for PDF storage if needed)

### Python Packages to Consider
- `celery` - Task queue management
- `redis` - Caching and task broker
- `django-rest-framework` - API development
- `django-storages` - Cloud storage backends
- `python-magic` - File type validation
- `hashlib` - Checksum generation
- `httpx` - HTTP client for API calls
- `langchain` or similar - LLM abstraction

### Frontend Technologies
Original plan:
- Modern CSS framework (Bootstrap, Tailwind)
- JavaScript for interactivity
- HTMX for progressive enhancement
- ~~WebSockets/SSE for real-time updates~~

Developer-comment:
- Lead with CSS; use JavaScript where necessary.
- I like HTMX.
- No websockets.


## Next Steps

Each functional section above provides enough context for detailed implementation planning. When implementing a specific section, consider:

1. Creating detailed technical specifications
2. Defining data flow diagrams
3. Identifying specific API contracts
4. Creating UI/UX mockups
5. Writing test scenarios
6. Documenting configuration requirements

This high-level plan ensures all major components are identified and their relationships understood, enabling focused implementation of individual sections while maintaining overall system coherence.

---

# Developer-comment: 

- This is great.

- I'm going to first start with a very simple webapp-form (no-API) uploader, and a simple webpage response (no LLM yet).

- Very initial functionality: 
    - user uploads a PDF.
    - file is checked that it is a PDF.
    - checksum is generated and saved, via a model, to the initial sqlite database.
    - veraPDF is run on the PDF (for accessibility-check).
    - veraPDF json is saved, via a model, to the sqlite database.
    - the verapdf json is parsed to generate a report showing two things:
        - a simple yes/no pass/fail for accessibility.
        - a list of all the accessibility issues found.

---
