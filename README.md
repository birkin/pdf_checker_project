_(under construction)_

[![CI tests](https://github.com/birkin/pdf_checker_project/actions/workflows/ci_tests.yaml/badge.svg)](https://github.com/birkin/pdf_checker_project/actions/workflows/ci_tests.yaml)

# PDF Checker Project

## Purpose

This webapp will serve two purposes.

It will allow Library staff -- and perhaps others in the Brown community -- to upload a PDF and get back a [veraPDF][verapdf_link] accessibility report.

It will also offer an API endpoint for Library services to check the accessibility of a PDF.

[verapdf_link]: <https://verapdf.org>


## Vision / User

A user wants to get an accessibility report for a PDF.

The user uploads the pdf to the webapp.

The webapp runs an accessibility-check on the pdf using veraPDF.

The webapp runs the report through an LLM to generate a human-readable report.

The webapp returns the accessibility report to the user.


## Vision / API

Our programming-team wants to get accessibility reports for lots of PDFs.

We write a script to sent lots of PDFs to the API endpoint.

The API endpoint code runs an accessibility-check on the pdf using veraPDF.

Depending on the API flags, the API endpoint returns any combination of:
- a binary accessible/not-accessible response
- the json-accessibility-report
- the human-readable accessibility-report


## Implementation features

- The webapp should create a checksum for the uploaded pdf, so if the same pdf is uploaded again, with the same formfields/api-flags, the webapp can return the same accessibility-report.

- The checksum / effective-cache feature implies the veraPDF accessibility-report should be stored in a database.

- LLM-handling... The webapp will need to be able to call different models (for development/cost/server reasons). Since different models may have different context-sizes, the code will need to differentially handle the prompt-preparation for differing context-sizes.

---
