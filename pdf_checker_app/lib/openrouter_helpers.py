"""
Helper functions for OpenRouter API integration.

Called by:
    - pdf_checker_app.lib.sync_processing_helpers (synchronous attempts)
    - scripts.process_openrouter_summaries (cron background processing)
"""

import json
import logging
import os
from datetime import datetime, timezone

import httpx
from django.utils import timezone as django_timezone

from pdf_checker_app.models import OpenRouterSummary

log = logging.getLogger(__name__)

OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

PROMPT = """
# Context: 
- I ran a pdf accessibility report using veraPDF, using the `PDF/UA-1 - Accessibility (PDF 1.7)` profile.
- I got back this json output:

```
{verapdf_json_output}
```

# Task: 
- Imagine a user has uploaded this pdf to a customized pdf-accessibility checker.
- Imagine the user is not a developer, and not extremely technically savvy, but does have access to a couple of the most common pdf-editing tools like Acrobat.
- Analyze the validation-result json file above.
- Main task: Come up with some helpful suggestions to the user about how to start fixing the errors.

## Regarding your helpful-suggestions:
- Focus on the top three improvements that would give the most "bang for the buck", in terms of improving accessibility.
- Start the helpful-suggestions text like: "Here are some suggestions to improve the accessibility of your PDF."
- Do not mention or reference the report.
- It's ok to mention that there are other things that may need to be addressed, but the goal is to not overwhelm the user.
- Do not use jargon, like referring to "XMP". Instead, convey that some metadata needs to be improved.
- Do not invite followup questions.
- Do not include information the user will have seen. 
	- Here is information the user will have seen: ```Note: veraPDF may report thousands of "failed checks" -- but that does _not_ mean thousands of distinct problems. Think of a "failed check" as a repeated warning bell, not a separate task. Example: if the PDF lacks a language setting, or proper tagging, veraPDF will flag each affected text snippet or layout element, inflating totals. Remediation work should target a few root causes, which can clear thousands of checks quickly.```
	- So do not reiterate that information in your helpful-suggestions.
"""


def get_api_key() -> str:
    """
    Retrieves the OpenRouter API key from environment.
    """
    api_key: str = os.environ.get('OPENROUTER_API_KEY', '')
    return api_key


def get_model() -> str:
    """
    Retrieves the OpenRouter model from environment.
    """
    model: str = os.environ.get('OPENROUTER_MODEL', '')
    return model


def filter_down_failure_checks(raw_verapdf_json: dict) -> dict:
    """
    Filters down veraPDF JSON by keeping only one unique check per rule in 'checks' arrays.
    """
    return prune_checks_recursive(raw_verapdf_json)


def prune_checks_recursive(value: object) -> object:
    """
    Recursively processes the JSON, keeping one unique check per rule in 'checks' arrays.
    """
    pruned: object = value

    if isinstance(value, dict):
        new_dict: dict[str, object] = {}
        for key, child in value.items():
            if key == 'checks' and isinstance(child, list):
                new_dict[key] = filter_unique_checks(child)
            else:
                new_dict[key] = prune_checks_recursive(child)
        pruned = new_dict

    elif isinstance(value, list):
        new_list: list[object] = []
        for child in value:
            new_list.append(prune_checks_recursive(child))
        pruned = new_list

    return pruned


def filter_unique_checks(checks: list[object]) -> list[object]:
    """
    Filters a checks array to keep only one representative check.
    """
    result: list[object] = []
    if len(checks) > 0:
        result = [checks[0]]
    return result


def build_prompt(verapdf_json: dict) -> str:
    """
    Builds the prompt for OpenRouter based on veraPDF results.
    """
    verapdf_json_str = json.dumps(verapdf_json, indent=2)
    prompt = PROMPT.format(verapdf_json_output=verapdf_json_str)
    log.debug(f'prompt, ``{prompt}``')
    return prompt


def call_openrouter(prompt: str, api_key: str, model: str, timeout_seconds: float) -> dict:
    """
    Calls the OpenRouter API with the given prompt.
    Returns the raw response JSON.

    Raises:
        httpx.TimeoutException: If the request exceeds timeout_seconds.
        httpx.HTTPStatusError: If the API returns an error status.

    Note: Only one of our servers requires a non-default certificate to be specified,
          so the SYSTEM_CA_BUNDLE environment variable is implemented optionally.
    """
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://library.brown.edu',
        'X-Title': 'PDF Accessibility Checker',
    }

    payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}]}

    client_kwargs = {'timeout': timeout_seconds}
    SYSTEM_CA_BUNDLE = os.environ.get('SYSTEM_CA_BUNDLE')  # path to a non-default certificate-authority bundle file
    if SYSTEM_CA_BUNDLE:
        client_kwargs['verify'] = SYSTEM_CA_BUNDLE

    with httpx.Client(**client_kwargs) as client:
        response = client.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        jsn_response = response.json()
        log.debug(f'jsn_response, ``{jsn_response}``')
        return jsn_response

    ## end def call_openrouter()


def parse_openrouter_response(response_json: dict) -> dict:
    """
    Parses the OpenRouter response and extracts relevant fields.
    """
    result = {
        'summary_text': '',
        'openrouter_response_id': response_json.get('id', ''),
        'provider': response_json.get('provider', ''),
        'model': response_json.get('model', ''),
        'finish_reason': '',
        'openrouter_created_at': None,
        'prompt_tokens': None,
        'completion_tokens': None,
        'total_tokens': None,
    }

    ## Extract summary text from choices
    choices = response_json.get('choices', [])
    if choices:
        choice = choices[0]
        message = choice.get('message', {})
        result['summary_text'] = message.get('content', '')
        result['finish_reason'] = choice.get('finish_reason', '')

    ## Extract usage info
    usage = response_json.get('usage', {})
    result['prompt_tokens'] = usage.get('prompt_tokens')
    result['completion_tokens'] = usage.get('completion_tokens')
    result['total_tokens'] = usage.get('total_tokens')

    ## Extract created timestamp
    created = response_json.get('created')
    if created:
        utc_dt = datetime.fromtimestamp(created, tz=timezone.utc)
        result['openrouter_created_at'] = django_timezone.make_naive(utc_dt)

    return result

    ## end def parse_openrouter_response()


def persist_openrouter_summary(summary: OpenRouterSummary, response_json: dict, parsed: dict) -> None:
    """
    Persists the OpenRouter response to the summary model instance.
    """
    summary.raw_response_json = response_json
    summary.summary_text = parsed['summary_text']
    summary.openrouter_response_id = parsed['openrouter_response_id']
    summary.provider = parsed['provider']
    summary.model = parsed['model']
    summary.finish_reason = parsed['finish_reason']
    summary.openrouter_created_at = parsed['openrouter_created_at']
    summary.prompt_tokens = parsed['prompt_tokens']
    summary.completion_tokens = parsed['completion_tokens']
    summary.total_tokens = parsed['total_tokens']
    utc_now = datetime.now(tz=timezone.utc)
    naive_now = django_timezone.make_naive(utc_now)
    summary.status = 'completed'
    summary.completed_at = naive_now
    summary.error = None
    summary.save()
