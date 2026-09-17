"""Validate the actual Streamlit summary and retain JSON beside its RAW evidence."""
import json
from pathlib import Path


def check_summary(app, required=False):
    summaries = [json.loads(item.value) if isinstance(item.value, str) else item.value for item in app.json]
    if required:
        assert summaries, 'Analysis Summary JSON was not rendered'
    for summary in summaries:
        assert {'analysis_type','simulation_conditions','measured_facts','derived_facts','warnings',
                'comparison_results','evidence'} <= summary.keys()
        text = json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2)
        assert any(item.value == 'Analysis Summary' for item in app.subheader)
        evidence = summary['evidence']
        for path in evidence.get('graph_paths', []):
            assert Path(path).is_file(), path
        raw = evidence.get('raw_file') or next((p['raw_file'] for p in evidence.get('points', []) if p['raw_file']), None)
        if raw and Path(raw).is_file():
            Path(raw).with_name('analysis_summary.json').write_text(text, encoding='utf-8')
    return summaries[-1] if summaries else None
