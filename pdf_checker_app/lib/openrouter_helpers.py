"""
Helper functions for OpenRouter API integration.

Called by:
    - pdf_checker_app.lib.sync_processing_helpers (synchronous attempts)
    - scripts.process_openrouter_summaries (cron background processing)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from django.conf import settings as project_settings
from django.utils import timezone as django_timezone

from pdf_checker_app.models import OpenRouterSummary

log = logging.getLogger(__name__)

OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

PROMPT_FILE_PATH = Path(__file__).resolve().parent / 'prompt.md'


def load_prompt_template() -> str:
    """
    Loads the OpenRouter prompt template from disk.
    """
    prompt_text = PROMPT_FILE_PATH.read_text(encoding='utf-8')
    return prompt_text


def get_api_key() -> str:
    """
    Retrieves the OpenRouter API key from environment.
    """
    return project_settings.OPENROUTER_API_KEY


def get_model_order() -> list[str]:
    """
    Retrieves the OpenRouter model order from environment.
    """
    return list(project_settings.OPENROUTER_MODEL_ORDER)


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
    prompt_template = load_prompt_template()
    prompt = prompt_template.format(verapdf_json_output=verapdf_json_str)
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
    system_ca_bundle = project_settings.SYSTEM_CA_BUNDLE
    if system_ca_bundle:
        client_kwargs['verify'] = system_ca_bundle

    with httpx.Client(**client_kwargs) as client:
        response = client.post(OPENROUTER_API_URL, headers=headers, json=payload)
        log.debug(f'response, ``{response}``')
        if response.is_error:
            log.error(
                'OpenRouter request failed with status=%s, model=%s, response=%s',
                response.status_code,
                model,
                response.text,
            )
        response.raise_for_status()
        jsn_response = response.json()
        log.debug(f'jsn_response, ``{jsn_response}``')
        return jsn_response

    ## end def call_openrouter()


def call_openrouter_with_model_order(
    prompt: str,
    api_key: str,
    model_order: list[str],
    timeout_seconds: float,
) -> dict:
    """
    Calls OpenRouter with models in the provided order until one succeeds.
    """
    last_exception: Exception | None = None
    response_json: dict = {}
    log.debug('OpenRouter model order: %s', model_order)

    for index, model in enumerate(model_order, start=1):
        try:
            log.info('OpenRouter attempt %s/%s with model=%s', index, len(model_order), model)
            response_json = call_openrouter(prompt, api_key, model, timeout_seconds)
            last_exception = None
            break
        except Exception as exc:
            last_exception = exc
            log.warning('OpenRouter call failed for model=%s, trying next if available', model)

    if last_exception is not None:
        raise last_exception

    return response_json

    ## end def call_openrouter_with_model_order()


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
