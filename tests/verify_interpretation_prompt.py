"""Export local prompt examples from saved real summaries; no simulation/API."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from ai_interpretation import build_interpretation_prompt, prompt_as_text


def numerical_facts(value, prefix=()):
    if isinstance(value, dict):
        return {path: number for key, item in value.items() for path, number in numerical_facts(item, prefix+(key,)).items()}
    if isinstance(value, list):
        return {path: number for i, item in enumerate(value) for path, number in numerical_facts(item, prefix+(i,)).items()}
    return {prefix: value} if type(value) in (int, float) else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('summaries', nargs='+', type=Path)
    args = parser.parse_args()
    folder = PROJECT/'simulation_output'/f'interpretation_prompt_verification_{uuid4().hex}'
    folder.mkdir()
    for index, path in enumerate(args.summaries):
        before = path.read_bytes()
        summary = json.loads(before)
        prompt = build_interpretation_prompt(summary)
        prepared = prompt['user']['analysis_summary']
        for key in ('measured_facts','derived_facts','comparison_results','warnings'):
            assert numerical_facts(summary.get(key)) == numerical_facts(prepared.get(key)), key
        text = prompt_as_text(prompt)
        assert 'C:\\Users\\' not in text and 'C:/Users/' not in text
        assert path.read_bytes() == before
        name = f'{index+1}_{summary["analysis_type"].replace(" ","_")}'
        json_path = folder/f'{name}.json'
        json_path.write_text(json.dumps(prompt,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
        (folder/f'{name}.txt').write_text(text,encoding='utf-8')
        assert json.loads(json_path.read_text(encoding='utf-8')) == prompt
        print('PASS: exact numerical facts, strict JSON, local paths omitted, original summary unchanged:', json_path)
    print('EVIDENCE:', folder)


if __name__ == '__main__':
    main()
