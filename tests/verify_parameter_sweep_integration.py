"""Actual approved AC/Transient/DC sweeps, plus a real middle-point failure."""
import ast
from summary_assertions import check_summary
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4

import numpy as np
from PyLTSpice import AscEditor
from streamlit.testing.v1 import AppTest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from parameter_sweep import parse_parameter_sweep, component_value
from parameter_sweep_execution import (run_parameter_sweep, comparison_table, comparison_summary,
                                       comparison_figures, overlay_figure)
from simulation_runner import run_ltspice
from analysis_summary import build_sweep_summary

AC_SETTINGS = dict(sweep_type='Decade', points=100, start_frequency='10 Hz', stop_frequency='1 MHz')


def uploaded(data, name):
    file = io.BytesIO(data)
    file.name = name
    return file


def run_ui(app, data, name, request, fields):
    app.file_uploader[0].set_value((name, data, 'text/plain')).run()
    app.text_area[0].set_value(request).run()
    app.button[0].click().run()
    for key, value in fields.items():
        app.text_input(key=key).set_value(value).run()
    assert not app.exception, [error.message for error in app.exception]
    assert not app.error, [error.value for error in app.error]
    button = next(b for b in app.button if b.label == 'Run Parameter Sweep')
    assert button.disabled
    captured = []
    def execute(*args, **kwargs):
        result = run_parameter_sweep(*args, **kwargs)
        captured.extend(result)
        return result
    with patch('parameter_sweep_execution.run_parameter_sweep', side_effect=execute):
        app.checkbox(key='parameter_approved').check().run()
        next(b for b in app.button if b.label == 'Run Parameter Sweep').click().run(timeout=180)
    assert not app.exception and not app.error, [error.value for error in app.error]
    assert captured and len(app.dataframe) == 2
    summary = check_summary(app, required=True)
    assert len(summary['measured_facts']['points']) == len(captured)
    assert 'RAW' not in app.dataframe[0].value.columns and 'LOG' not in app.dataframe[0].value.columns
    assert any(item.label == 'Point Details / Evidence' for item in app.expander)
    for point in captured:
        if point.raw:
            assert any(point.raw in item.value for item in app.text)
        if point.log:
            assert any(point.log in item.value for item in app.text)
    return captured


def verify_copies(points, original, name, component):
    assert len({point.raw for point in points}) == len(points)
    for point in points:
        assert point.result is not None, (point.label, point.status, point.notes)
        raw, log = Path(point.raw), Path(point.log)
        assert raw.is_file() and log.is_file() and raw.stat().st_size and log.stat().st_size
        copy = PROJECT/'simulation_input'/raw.parent.name/name
        editor = AscEditor(copy)
        assert component_value(editor.get_component_value(component)) == component_value(point.label)
        assert point.directive in copy.read_text(encoding='utf-8')
    assert original  # callers separately compare the original file bytes


def save_results(folder, label, points, component, analysis):
    rows = comparison_table(points, component)
    (folder/f'{label}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder/f'{label}_summary.json').write_text(json.dumps(comparison_summary(points), ensure_ascii=False, indent=2), encoding='utf-8')
    for index, figure in enumerate(comparison_figures(points, component).values()):
        figure.savefig(folder/f'{label}_measurement_{index}.png', dpi=130)
    figure = overlay_figure(points, component, analysis)
    if figure:
        figure.savefig(folder/f'{label}_overlay.png', dpi=130)
    summary = build_sweep_summary(points, component, analysis,
                                  graph_paths=sorted(folder.glob(f'{label}_*.png')))
    (folder/f'{label}_analysis_summary.json').write_text(json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    if label == 'mosfet_resistor_ac':
        gain = summary['derived_facts']['trends']['Low-Frequency Gain [dB]']
        assert gain['segments'][0]['stop_parameter'] == 2000
        assert any(w['code']=='large_trend_reversal' and w['parameter_value']==5000 for w in summary['warnings'])
        assert any(w['code']=='bandwidth_not_found' and w['parameter_value']==5000 for w in summary['warnings'])
    elif label == 'mosfet_capacitor_transient':
        assert summary['derived_facts']['trends']['Voltage Gain: Voltage Gain [V/V]']['monotonic'] == 'decreasing'
    print(label, json.dumps([{component: row[component], 'Status': row['Status'], **point.metrics}
                             for point,row in zip(points, rows)], ensure_ascii=False))


def main():
    tree = ast.parse((PROJECT/'test_ltspice.py').read_text(encoding='utf-8'))
    source = Path(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id=='ASC_FILE' for target in node.targets)))
    original = source.read_bytes()
    app = AppTest.from_file(str(PROJECT/'app.py'), default_timeout=60).run()
    ac = run_ui(app, original, source.name,
                'R1을 500, 1k, 2k, 5k로 바꿔가며 AC simulation하고 gain과 -3 dB bandwidth 비교',
                {'review_target':'V(vout)', 'review_reference':'V(vin)', 'review_start_frequency':'10 Hz', 'review_stop_frequency':'1 MHz'})
    verify_copies(ac, original, source.name, 'R1')
    folder = PROJECT/'simulation_output'/f'parameter_sweep_verification_{uuid4().hex}'
    folder.mkdir()
    save_results(folder, 'mosfet_resistor_ac', ac, 'R1', 'AC')

    transient = run_ui(app, original, source.name,
                       'C1을 10n부터 30n까지 10n 간격으로 바꿔가며 transient simulation하고 output swing과 gain 비교',
                       {'review_target':'V(vout)', 'review_reference':'V(vin)', 'review_stop_time':'2 ms',
                        'review_start_saving_time':'1 ms', 'review_maximum_timestep':'1 us'})
    verify_copies(transient, original, source.name, 'C1')
    assert all(point.status=='OK' for point in transient)
    save_results(folder, 'mosfet_capacitor_transient', transient, 'C1', 'Transient')

    divider = PROJECT/'tests/fixtures/dc_divider.asc'
    divider_original = divider.read_bytes()
    dc = run_ui(app, divider_original, divider.name,
                'R1을 1k, 2k로 바꿔가며 DC simulation minimum maximum 비교',
                {'review_target':'V(out)', 'review_sweep_source':'V1', 'review_dc_start':'0 V',
                 'review_dc_stop':'5 V', 'review_dc_step':'10 mV'})
    verify_copies(dc, divider_original, divider.name, 'R1')
    np.testing.assert_allclose([p.metrics['Maximum [V]'] for p in dc], [2.5,5/3], atol=1e-6)
    save_results(folder, 'divider_dc', dc, 'R1', 'DC Sweep')

    # Deliberately break only the middle upload's model; actual LTspice fails.
    def failing_middle(file, **kwargs):
        value = component_value(kwargs['component_update'][1])
        if value == 2000:
            assert b'FQB55N10' in file.getvalue()
            file = uploaded(file.getvalue().replace(b'FQB55N10', b'MODEL_MISSING_FOR_SWEEP_TEST'), file.name)
        return run_ltspice(file, **kwargs)
    conditions = parse_parameter_sweep('R1을 1k, 2k, 5k로 바꿔가며 AC gain과 bandwidth 비교')
    failures = run_parameter_sweep(uploaded(original, source.name), conditions, AC_SETTINGS,
                                    'V(vout)', 'V(vin)', approved=True, runner=failing_middle)
    assert failures[0].result is not None and failures[2].result is not None
    assert failures[1].status == 'Simulation Failed' and not failures[1].metrics
    assert Path(failures[1].log).is_file()
    save_results(folder, 'partial_failure', failures, 'R1', 'AC')
    assert source.read_bytes() == original and divider.read_bytes() == divider_original
    print('PASS: independent copies, original bytes preserved, all successful points have RAW/LOG; actual middle failure did not stop final point')
    print('EVIDENCE:', folder)


if __name__ == '__main__':
    main()
