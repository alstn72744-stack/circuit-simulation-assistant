"""Explicit, bounded interpretation calls; no simulator, RAW access or calculation.

Only a canonical Prompt 008A payload is accepted. Numerical validation is a
lexical evidence check, not proof of semantic correctness or physical causality.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import json
import math
import os
import re

from ai_interpretation import build_interpretation_prompt

DEFAULT_MODEL = 'gpt-4.1-mini'
SECTIONS = {
    'confirmed_results': 'Confirmed Results',
    'interpretation': 'Interpretation',
    'additional_insights': 'Additional Insights',
    'warnings_uncertainty': 'Warnings / Uncertainty',
    'suggested_next_checks': 'Suggested Next Checks',
}
OUTPUT_SCHEMA = {'type': 'object', 'properties': {
    key: {'type': 'array', 'items': {'type': 'string'}} for key in SECTIONS},
    'required': list(SECTIONS), 'additionalProperties': False}
OUTPUT_INSTRUCTION = ('Return the required JSON fields instead of Markdown headings. '
    'Each field corresponds to its named section in the system rules. '
    'Label every interpretation item as inference/hypothesis (추론/가설). '
    'Use empty lists when evidence is insufficient. Do not add new numbers.')
MOCK_RESPONSE = {key: [] for key in SECTIONS}
MOCK_RESPONSE.update(
    confirmed_results=['Mock mode: 구조화 응답 표시를 확인하는 예시입니다.'],
    interpretation=['가설: 실제 회로 해석은 수행하지 않았습니다.'],
    warnings_uncertainty=['Mock 응답이며 실제 모델의 해석 결과가 아닙니다.'],
    suggested_next_checks=['검증된 Analysis Summary와 측정 조건을 검토하세요.'])


@dataclass(frozen=True)
class LLMConfig:
    provider: str = 'openai'
    model: str = DEFAULT_MODEL
    api_key: str = field(default='', repr=False, compare=False)
    temperature: float | None = None  # Omitted by default for model compatibility.
    timeout_seconds: float = 45
    max_output_tokens: int = 2500
    max_input_characters: int = 60000


def load_config(secrets=None, environ=None):
    """Environment takes precedence; secrets are a caller-supplied mapping."""
    env = os.environ if environ is None else environ
    secrets = {} if secrets is None else secrets
    def setting(key, default):
        return env.get(key) or secrets.get(key, default)
    temperature = setting('LLM_TEMPERATURE', None)
    return LLMConfig(provider=str(setting('LLM_PROVIDER', 'openai')).strip().lower(),
        model=str(setting('OPENAI_MODEL', DEFAULT_MODEL)).strip(),
        api_key=str(setting('OPENAI_API_KEY', '')).strip(),
        temperature=None if temperature in (None, '') else float(temperature),
        timeout_seconds=float(setting('LLM_TIMEOUT_SECONDS', 45)),
        max_output_tokens=int(setting('LLM_MAX_OUTPUT_TOKENS', 2500)),
        max_input_characters=int(setting('LLM_MAX_INPUT_CHARACTERS', 60000)))


def request_content(prompt):
    """Reject altered instructions/unfiltered objects before any provider call."""
    try:
        canonical = build_interpretation_prompt(prompt['user']['analysis_summary'])
        # Preparation notices describe the first sanitization and may differ.
        if prompt['system'] != canonical['system'] or prompt['user'] != canonical['user']:
            raise ValueError('Prompt must come from Prepare AI Interpretation.')
        return dict(instructions=prompt['system'] + '\n\n' + OUTPUT_INSTRUCTION,
                    input=json.dumps(prompt['user'], ensure_ascii=False, allow_nan=False))
    except (KeyError, TypeError, ValueError, RecursionError) as error:
        raise ValueError('Invalid interpretation prompt; prepare it again.') from error


def input_estimate(prompt):
    content = request_content(prompt)
    # Includes schema text; UTF-8 byte count is a conservative rough estimate,
    # not a tokenizer count or an API billing quote (especially for Korean).
    text = content['instructions'] + content['input'] + json.dumps(OUTPUT_SCHEMA)
    return {'characters': len(text), 'token_estimate': len(text.encode('utf-8'))}


NUMBER = re.compile(r'(?<![A-Za-z0-9_.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?|(?<![A-Za-z0-9_.])[-+]?\.\d+(?:[eE][-+]?\d+)?')
UNIT = re.compile(r'\s*(V/V|dB|GHz|MHz|kHz|Hz|mV|uV|µV|V|mA|uA|µA|A|ms|us|µs|ns|s|nF|pF|uF|µF|F|kOhm|Ohm|kΩ|Ω|%)(?![A-Za-z])')


def _numbers(text):
    text = text.replace('−', '-')
    for match in NUMBER.finditer(text):
        unit = UNIT.match(text, match.end())
        yield Decimal(match.group().replace(',', '')), unit.group(1) if unit else '', match.group()


def validate_numerical_claims(response, summary):
    """Exact Decimal membership; no rounding, unit conversion or auto-correction.

    Includes supplied labels/definitions so '-3 dB' is not a new measurement.
    Does not establish that a known number belongs to the claimed trace/point.
    Unsupported notation/units can require human review; no causal NLP check.
    """
    numbers, quantities = set(), set()
    def collect(value, unit=''):
        if type(value) in (int, float) and math.isfinite(value):
            number = Decimal(str(value))
            numbers.add(number)
            if unit:
                quantities.add((number, unit))
        elif isinstance(value, str):
            for number, text_unit, _ in _numbers(value):
                numbers.add(number)
                if text_unit:
                    quantities.add((number, text_unit))
        elif isinstance(value, list):
            for item in value:
                collect(item, unit)
        elif isinstance(value, dict):
            if value.get('status') in ('Simulation Failed', 'Analysis Failed', 'unavailable'):
                # Preserve labels/status, but never accept stale unavailable values.
                for key in value:
                    collect(key)
                return
            record_unit = value.get('unit', unit)
            for key, item in value.items():
                collect(key)
                suffix = re.search(r'\[([^]]+)\]$', key)
                child_unit = suffix.group(1) if suffix else record_unit
                if key == 'relative_change_percent':
                    child_unit = '%'
                collect(item, child_unit)
    for key in ('simulation_conditions', 'measured_facts', 'derived_facts', 'comparison_results', 'warnings'):
        collect(summary.get(key, {}))
    warnings = []
    for section, lines in response.items():
        for index, line in enumerate(lines):
            for number, unit, token in _numbers(line):
                code = ('unsupported_number' if number not in numbers else
                        'unverified_unit' if unit and (number, unit) not in quantities else None)
                if code:
                    item = dict(code=code, section=section, item_index=index, token=token, unit=unit,
                                message='Numerical claim is not supported in this form by the supplied Summary.')
                    if item not in warnings:
                        warnings.append(item)
    return warnings


def parse_response(text, summary):
    """Invalid schema stays raw fallback, never presented as confirmed facts."""
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or set(data) != set(SECTIONS):
            raise ValueError('Unexpected fields')
        if not all(type(lines) is list and all(type(line) is str for line in lines) for lines in data.values()):
            raise ValueError('Expected string lists')
    except (ValueError, TypeError):
        return dict(status='malformed_response', data=None, raw_text=text,
                    warnings=[dict(code='malformed_response', message='Invalid structured response; raw text is unverified.')]
                    + validate_numerical_claims({'raw_text': [text]}, summary))
    warnings = validate_numerical_claims(data, summary)
    return dict(status='validation_warning' if warnings else 'completed', data=data,
                raw_text=text, warnings=warnings)


def _error(code, message):
    return dict(status='error', data=None, raw_text='', warnings=[], error_code=code, error=message)


def _create_openai(config):
    from openai import OpenAI
    # No automatic retries: each button action authorizes one request only.
    return OpenAI(api_key=config.api_key, timeout=config.timeout_seconds, max_retries=0,
                  base_url='https://api.openai.com/v1')


def interpret_analysis(prompt_payload, config, *, client=None):
    """Call only on explicit UI action; fake client injection never needs network."""
    if config.provider not in ('openai', 'mock'):
        return _error('configuration', 'Unsupported LLM provider.')
    if config.provider == 'openai' and not config.api_key:
        return _error('missing_api_key', 'API key not configured')
    if (not config.model.strip() or not 0 < config.timeout_seconds <= 120
            or not 1 <= config.max_output_tokens <= 16000
            or not 1 <= config.max_input_characters <= 200000
            or (config.temperature is not None and not 0 <= config.temperature <= 2)):
        return _error('configuration', 'Invalid LLM configuration.')
    try:
        content = request_content(prompt_payload)
        if input_estimate(prompt_payload)['characters'] > config.max_input_characters:
            return _error('input_too_large', 'Prompt exceeds the configured input limit. Reduce sweep points; no data was sent.')
    except ValueError:
        return _error('invalid_prompt', 'Invalid interpretation prompt; prepare it again.')
    summary = prompt_payload['user']['analysis_summary']
    if config.provider == 'mock':
        result = parse_response(json.dumps(MOCK_RESPONSE, ensure_ascii=False), summary)
    else:
        try:
            kwargs = dict(model=config.model, **content, store=False,
                max_output_tokens=config.max_output_tokens,
                text={'format': {'type': 'json_schema', 'name': 'analysis_interpretation',
                                 'strict': True, 'schema': OUTPUT_SCHEMA}})
            if config.temperature is not None:
                kwargs['temperature'] = config.temperature
            if client is None:
                with _create_openai(config) as api:
                    response = api.responses.create(**kwargs)
            else:
                response = client.responses.create(**kwargs)
            text = getattr(response, 'output_text', '')
            if not isinstance(text, str):
                text = ''
            if getattr(response, 'status', None) != 'completed':
                result = dict(status='incomplete_response', data=None, raw_text=text,
                    warnings=[dict(code='incomplete_response', message='Response did not complete; raw text is unverified.')]
                    + validate_numerical_claims({'raw_text': [text]}, summary))
            elif any(getattr(part, 'type', '') == 'refusal' for item in getattr(response, 'output', [])
                     for part in getattr(item, 'content', [])):
                return _error('refusal', 'The provider declined this interpretation request.')
            else:
                result = parse_response(text, summary)
        except Exception as error:
            # Do not expose provider exception text: it may contain credentials,
            # request content or local paths. No automatic fallback API call.
            name, status = type(error).__name__, getattr(error, 'status_code', None)
            if isinstance(error, ImportError):
                return _error('dependency_missing', 'OpenAI SDK is not installed. Install requirements-llm.txt or select mock.')
            if status in (401, 403) or name in ('AuthenticationError', 'PermissionDeniedError'):
                return _error('authentication', 'Authentication failed. Check API key and model access.')
            if status == 429 or name == 'RateLimitError':
                return _error('rate_limit', 'Rate limit or quota reached. Review your account and retry manually.')
            if isinstance(error, TimeoutError) or name == 'APITimeoutError':
                return _error('timeout', 'The API request timed out. Retry manually if needed.')
            if isinstance(error, ConnectionError) or name == 'APIConnectionError':
                return _error('network', 'Network connection failed.')
            return _error('provider_error', 'Provider request failed. Check model/configuration and try again manually.')
    result.update(provider=config.provider, model=config.model)
    return result
