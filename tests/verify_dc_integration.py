"""Streamlit DC workflow checks; --real-ltspice runs committed test-only ASC fixtures."""
import argparse
from summary_assertions import check_summary
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
import streamlit as st
from streamlit.testing.v1 import AppTest
from PyLTSpice import RawRead

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from dc_result_analysis import read_dc_result, dc_figure

REQUEST = 'V1을 0 V부터 5 V까지 10 mV 간격으로 sweep하고 V(out)의 minimum과 maximum, V1 = 3 V일 때 값을 구해줘.'


def run_button(app):
    return next(button for button in app.button if button.label == 'Run Simulation')


def check(app):
    check_summary(app, required=any(item.value == 'Simulation completed' for item in app.success))
    assert not app.exception, [item.message for item in app.exception]


def prepare(app, name, data, request=REQUEST):
    app.file_uploader[0].set_value((name, data, 'text/plain')).run()
    app.text_area[0].set_value(request).run()
    app.button[0].click().run()
    check(app)
    assert app.selectbox[0].value == 'DC Sweep' and run_button(app).disabled


def execute(app):
    before = set((PROJECT/'simulation_output').glob('*/*.raw'))
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check(app)
    assert not app.error, [item.value for item in app.error]
    assert app.success[0].value == 'Simulation completed'
    raw = next(p for p in set((PROJECT/'simulation_output').glob('*/*.raw'))-before if not p.name.endswith('.op.raw'))
    assert raw.stat().st_size > 0 and raw.with_suffix('.log').stat().st_size > 0
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--real-ltspice', action='store_true')
    args = parser.parse_args()
    app = AppTest.from_file(str(PROJECT/'app.py'), default_timeout=60)
    before = set((PROJECT/'simulation_input').glob('**/*'))
    with patch('PyLTSpice.AscEditor') as editor, patch('PyLTSpice.SpiceEditor') as netlist, patch('PyLTSpice.SimRunner') as runner:
        app.run()
        prepare(app, 'approval.asc', b'Version 4\n')
        assert app.code[0].value == '.dc V1 0 5 10m'
        assert app.text_input(key='review_dc_point').value == '3 V'
        original_button = st.button
        with patch('streamlit.button', side_effect=lambda label, **kwargs: True if label == 'Run Simulation' else original_button(label, **kwargs)):
            app.run()
        check(app)
        assert 'approve execution' in app.error[1].value
        app.run()
        for key, value in [('review_sweep_source', 'V2'), ('review_dc_step', '20 mV'),
                           ('review_dc_point', '2 V'), ('review_dc_comparison', 'V(in)')]:
            app.checkbox[0].check().run()
            app.text_input(key=key).set_value(value).run()
            assert not app.checkbox[0].value and run_button(app).disabled
        app.text_input(key='review_dc_stop').set_value('-1 V').run()
        assert app.checkbox[0].disabled and run_button(app).disabled
        editor.assert_not_called()
        netlist.assert_not_called()
        runner.assert_not_called()
        assert set((PROJECT/'simulation_input').glob('**/*')) == before
    print('PASS: DC parser, preview, approval guard/reset, invalid range; no writes/editor/simulator before approval')
    if not args.real_ltspice:
        return
    fixtures = PROJECT/'tests'/'fixtures'
    divider = fixtures/'dc_divider.asc'
    mirror = fixtures/'dc_current_mirror.asc'
    originals = {p: p.read_bytes() for p in (divider, mirror)}
    prepare(app, divider.name, originals[divider])
    raw = execute(app)
    result = read_dc_result(raw, 'V(out)', measurements=['Minimum', 'Maximum', 'Value at Sweep Point'], point=3, sweep_source='V1')
    assert len(result.sweep) == 501
    np.testing.assert_allclose(result.sweep[[0,-1]], [0,5], atol=1e-10)
    np.testing.assert_allclose(result.target, result.sweep/2, atol=1e-6)
    assert abs(result.point_value-1.5) < 1e-6 and len(app.metric) == 3
    assert app.code[-1].value == '.dc V1 0 5 10m'
    saved = PROJECT/'simulation_input'/raw.parent.name/divider.name
    text = saved.read_text()
    assert '.dc V1 0 5 10m' in text and '.tran' not in text and '.param fixture=1' in text
    assert (raw.parent/'dc_sweep.png').stat().st_size > 0
    dc_figure(result).savefig(raw.parent/'dc_sweep_verification.png', dpi=140)
    print(f'PASS: divider .dc V1 0 5 10m; samples={len(result.sweep)}; METRICS={result.metrics}; RAW={raw}; LOG={raw.with_suffix(".log")}')

    # Review edits must reach the actual simulator, including negative sweep values.
    app.text_input(key='review_dc_start').set_value('-1 V').run()
    app.text_input(key='review_dc_stop').set_value('4 V').run()
    app.text_input(key='review_dc_step').set_value('100 mV').run()
    edited = execute(app)
    axis = RawRead(edited).get_trace(0).get_wave()
    np.testing.assert_allclose(axis[[0,-1]], [-1,4], atol=1e-10)
    assert app.code[-1].value == '.dc V1 -1 4 100m'
    print(f'PASS: edited range/step applied; RAW={edited}')

    # A separate in-memory fixture variant verifies current-source sweep units.
    # current.asy pins are y=0/80; voltage.asy pins are y=16/96.
    current_source = originals[divider].replace(b'SYMBOL voltage 0 0 R0', b'SYMBOL current 0 16 R0').replace(b'InstName V1', b'InstName I1')
    prepare(app, 'dc_current_source.asc', current_source,
            'DC sweep I1 from 0 A to 1 mA step 10 uA; V(out) minimum maximum; I1 = 500 uA')
    current_raw = execute(app)
    assert 'I1 in 0 0' in current_raw.with_suffix('.net').read_text()
    current_result = read_dc_result(current_raw, 'V(out)', measurements=['Value at Sweep Point'], point=.0005, sweep_source='I1')
    np.testing.assert_allclose(current_result.target, -1000*current_result.sweep, atol=1e-6)
    assert abs(current_result.point_value+.5) < 1e-6
    assert app.code[-1].value == '.dc I1 0 1m 10u'
    print(f'PASS: current source .dc I1 0 1m 10u; V(out) at 500 uA={current_result.point_value} V; RAW={current_raw}')

    request = 'V1을 0 V부터 5 V까지 10 mV 간격으로 sweep하고 Id(M1)과 Id(M2)의 차이와 matching error를 비교해줘. V1 = 3 V일 때 값도 구해줘.'
    prepare(app, mirror.name, originals[mirror], request)
    mirror_raw = execute(app)
    measured = read_dc_result(mirror_raw, 'Id(M1)', 'Id(M2)', ['Difference', 'Matching Error', 'Value at Sweep Point'], 3, sweep_source='V1')
    # Independent Python scalar calculation, using the actual currents and signs.
    scalar_difference = np.array([float(a)-float(b) for a,b in zip(measured.target, measured.comparison)])
    scalar_error = np.array([abs(float(a)-float(b))/abs(float(a))*100 for a,b in zip(measured.target, measured.comparison)])
    np.testing.assert_allclose(measured.curves['Difference'][0], scalar_difference, rtol=1e-12, atol=1e-15)
    np.testing.assert_allclose(measured.curves['Matching Error'][0], scalar_error, rtol=1e-12, atol=1e-12)
    assert measured.target.min() > 1e-6 and len(app.dataframe) == 1
    index = int(np.argmin(abs(measured.sweep-3)))
    dc_figure(measured).savefig(mirror_raw.parent/'dc_mirror.png', dpi=140)
    print(f'PASS: current mirror .dc V1 0 5 10m; RAW={mirror_raw}; LOG={mirror_raw.with_suffix(".log")}')
    print(f'MIRROR @ {measured.sweep[index]} V: I1={measured.target[index]:.12g} A, I2={measured.comparison[index]:.12g} A, Difference={scalar_difference[index]:.12g} A, Matching Error={scalar_error[index]:.12g}%')
    print(f'MIRROR METRICS: {measured.metrics}; independent scalar comparison PASS')

    app.text_input(key='review_target').set_value('I(M1)').run()
    app.text_input(key='review_dc_comparison').set_value('I(M2)').run()
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check(app)
    assert app.success and 'I(M1)' in app.error[0].value and 'I(M2)' in app.error[0].value
    assert 'Id(M1)' in app.code[-1].value and not app.metric
    print('PASS: missing MOS I(M1)/I(M2) reported with actual Id(M1)/Id(M2); no implicit alias and no app crash')

    prepare(app, divider.name, originals[divider])
    app.text_input(key='review_sweep_source').set_value('Vmissing').run()
    with patch('PyLTSpice.SimRunner') as runner:
        app.checkbox[0].check().run()
        run_button(app).click().run(timeout=60)
        check(app)
        assert not app.success and 'Sweep source not found' in app.error[1].value
        runner.return_value.run_now.assert_not_called()
    print('PASS: nonexistent sweep source rejected before run_now')

    # Prompt 009A: exact real-user phrasing, source and requested point distinct.
    point_request = ('V2를 3.4 V부터 3.7 V까지 0.01 V 간격으로 DC sweep하고 '
                     'V(vout)의 변화를 보여줘. 3.55 V에서의 V(vout)도 구해줘.')
    point_circuit = originals[divider].replace(b'InstName V1', b'InstName V2').replace(b' out', b' vout')
    prepare(app, 'requested_point.asc', point_circuit, point_request)
    assert app.text_input(key='review_sweep_source').value == 'V2'
    assert app.text_input(key='review_dc_point').value == '3.55 V'
    point_raw = execute(app)
    point_result = read_dc_result(point_raw, 'V(vout)', measurements=['Value at Sweep Point'], point=3.55, sweep_source='V2')
    assert abs(point_result.point_value - 1.775) < 1e-6
    card = next(item for item in app.metric if item.label == 'Value at V2 = 3.55 V')
    assert card.value == '1.775 V'
    point_summary = app.session_state['completed_analysis_summary']
    assert point_summary['measured_facts']['Value at Sweep Point']['value'] == point_result.point_value
    print(f'PASS: requested V2=3.55 V card=1.775 V; exact Summary value={point_result.point_value}; RAW={point_raw}')

    broken = originals[mirror].replace(b'TESTNM NMOS', b'OTHER_MODEL NMOS')
    prepare(app, 'broken_mirror.asc', broken, request)
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check(app)
    assert not app.success and 'LTspice simulation failed' in app.error[0].value
    for path, data in originals.items():
        assert path.read_bytes() == data
    print('PASS: actual DC simulator failure displayed; original ASC fixtures preserved')


if __name__ == '__main__':
    main()
