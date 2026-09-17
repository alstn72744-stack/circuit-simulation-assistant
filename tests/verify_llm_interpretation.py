"""Exercise saved real summaries through mock and fake responses; never API calls."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from ai_interpretation import build_interpretation_prompt
from llm_client import LLMConfig, interpret_analysis, parse_response, SECTIONS


def measurement_lines(facts, prefix=''):
    for key, item in facts.items():
        if isinstance(item, dict) and 'value' in item and item['value'] is not None:
            yield f"{prefix}{key}: {item['value']} {item.get('unit', '')}"
        elif isinstance(item, dict):
            yield from measurement_lines(item, prefix+key+' / ')
        elif key == 'points':
            for row in item:
                if row['status'] not in ('OK','Partial Measurements'):
                    continue
                for name, value in row['measurements'].items():
                    if value is not None:
                        label, unit = name.rsplit(' [',1)
                        yield f"parameter={row['parameter_label']}; {label}: {value} {unit.rstrip(']')}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summaries', type=Path, nargs='+')
    args = parser.parse_args()
    folder = PROJECT/'simulation_output'/f'llm_mock_verification_{uuid4().hex}'
    folder.mkdir()
    for index, path in enumerate(args.summaries):
        before = path.read_bytes()
        summary = json.loads(before)
        prompt = build_interpretation_prompt(summary)
        mock = interpret_analysis(prompt, LLMConfig(provider='mock'))
        assert mock['status']=='completed', mock
        # A fake response quoting actual measured quantities must pass unchanged.
        data = {key: [] for key in SECTIONS}
        data['confirmed_results'] = list(measurement_lines(prompt['user']['analysis_summary']['measured_facts']))
        quoted = parse_response(json.dumps(data),prompt['user']['analysis_summary'])
        assert quoted['status']=='completed', quoted['warnings']
        assert quoted['data']==data
        data['confirmed_results'].append('Unsupported gain = 987654321.123 dB')
        unsupported = parse_response(json.dumps(data),prompt['user']['analysis_summary'])
        assert unsupported['status']=='validation_warning'
        result = dict(prompt=prompt, mock=mock, exact_measurement_response=quoted,
                      unsupported_claim_response=unsupported)
        dest = folder/f'{index+1}_{summary["analysis_type"].replace(" ","_")}.json'
        dest.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2),encoding='utf-8')
        assert json.loads(dest.read_text(encoding='utf-8'))==result
        assert path.read_bytes()==before
        print('PASS: mock, exact measured quantities, unsupported claim warning, Summary preserved:',dest)
    print('No real API calls.')


if __name__ == '__main__':
    main()
