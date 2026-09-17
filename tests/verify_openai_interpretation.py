"""Optional manual paid smoke test; never imported/run by unittest discovery.

python tests/verify_openai_interpretation.py SUMMARY.json --execute
Without an environment key or --execute this exits SKIP without a network call.
"""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_interpretation import build_interpretation_prompt
from llm_client import load_config, interpret_analysis, input_estimate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', type=Path, nargs='?')
    parser.add_argument('--execute', action='store_true', help='Authorize one real API request (may incur cost).')
    args = parser.parse_args()
    if not os.getenv('OPENAI_API_KEY'):
        print('SKIP: API key not configured (OPENAI_API_KEY).')
        return 0
    if not args.execute:
        print('SKIP: use --execute and a Summary JSON to authorize one real API request.')
        return 0
    if args.summary is None:
        parser.error('A verified Summary JSON is required.')
    prompt = build_interpretation_prompt(json.loads(args.summary.read_text(encoding='utf-8')))
    config = replace(load_config(), provider='openai')
    print('Model:', config.model, 'Input estimate:', input_estimate(prompt))
    result = interpret_analysis(prompt, config)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
