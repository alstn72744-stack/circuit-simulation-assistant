"""Re-read archived real RAWs; compare existing metrics and serialize summaries."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from analysis_summary import build_sweep_summary
from parameter_sweep_execution import SweepPoint, measure_point


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    output = PROJECT/'simulation_output'/f'analysis_summary_verification_{uuid4().hex}'
    output.mkdir()
    for name, component, analysis, measurements, settings in [
        ('mosfet_resistor_ac', 'R1', 'AC', ['Gain', '-3 dB Bandwidth'],
         dict(sweep_type='Decade', points=100, start_frequency='10 Hz', stop_frequency='1 MHz')),
        ('mosfet_capacitor_transient', 'C1', 'Transient', ['Voltage Gain', 'Output Swing'],
         dict(stop_time='2 ms', start_saving_time='1 ms', maximum_timestep='1 us')),
    ]:
        rows = json.loads((args.archive/f'{name}.json').read_text(encoding='utf-8'))
        points = []
        for row in rows:
            assert Path(row['RAW']).is_file() and Path(row['LOG']).is_file()
            result, metrics, notes = measure_point(row['RAW'], analysis, 'V(vout)', 'V(vin)', measurements, settings)
            for key, value in metrics.items():
                if value is None:
                    assert row[key] is None
                else:
                    np.testing.assert_allclose(value, row[key], rtol=1e-12, atol=1e-12)
            points.append(SweepPoint(row[component], row['Parameter Value'], row['Status'], metrics, notes,
                                     row['RAW'], row['LOG'], row['Directive'], result))
        summary = build_sweep_summary(points, component, analysis,
            conditions=dict(analysis_settings=settings, target_signal='V(vout)', reference_signal='V(vin)', measurements=measurements),
            graph_paths=sorted(args.archive.glob(f'{name}_*.png')))
        if component == 'R1':
            gain = summary['derived_facts']['trends']['Low-Frequency Gain [dB]']
            bandwidth = summary['derived_facts']['trends']['-3 dB Bandwidth [Hz]']
            assert gain['segments'][0]['direction'] == 'increasing'
            assert gain['segments'][0]['stop_parameter'] == 2000
            assert bandwidth['segments'][0]['direction'] == 'decreasing'
            assert any(w['code']=='large_trend_reversal' and w['parameter_value']==5000 for w in summary['warnings'])
            assert any(w['code']=='bandwidth_not_found' and w['parameter_value']==5000 for w in summary['warnings'])
        else:
            assert summary['derived_facts']['trends']['Voltage Gain: Voltage Gain [V/V]']['monotonic'] == 'decreasing'
        path = output/f'{name}_analysis_summary.json'
        path.write_text(json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
        assert json.loads(path.read_text(encoding='utf-8')) == summary
        print('PASS: archived RAW measurements unchanged, expected trends/warnings, strict JSON:', path)


if __name__ == '__main__':
    main()
