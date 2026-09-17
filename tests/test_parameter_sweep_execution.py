import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PyLTSpice import AscEditor
import numpy as np
import streamlit as st
from streamlit.testing.v1 import AppTest

from parameter_sweep import parse_parameter_sweep, generate_sweep_values, component_value
from parameter_sweep_execution import (SweepPoint, run_parameter_sweep, comparison_table, comparison_summary,
                                       comparison_figures, overlay_figure)
from simulation_runner import edit_component_value, run_ltspice

PROJECT = Path(__file__).resolve().parents[1]
AC = dict(sweep_type='Decade', points=100, start_frequency='10 Hz', stop_frequency='1 MHz')
REQUEST = 'R1을 1k, 2k, 5k로 바꿔가며 AC gain과 bandwidth 비교'


def upload():
    data = io.BytesIO((PROJECT/'tests/fixtures/dc_divider.asc').read_bytes())
    data.name = 'divider.asc'
    return data


class SweepExecutionTests(unittest.TestCase):
    def test_range_generation_and_non_grid_stop(self):
        conditions = parse_parameter_sweep('R1을 1k부터 10k까지 1k 간격으로 sweep AC')
        self.assertEqual(generate_sweep_values(conditions), list(range(1000, 10001, 1000)))
        conditions.update(start='1', stop='2', step='.3')
        self.assertEqual([str(v) for v in generate_sweep_values(conditions)], ['1.0', '1.3', '1.6', '1.9'])
        conditions['step'] = '0'
        with self.assertRaises(ValueError):
            generate_sweep_values(conditions)
        conditions.update(start='2', stop='1', step='.1')
        with self.assertRaises(ValueError):
            generate_sweep_values(conditions)
        conditions.update(start='1', stop='1000', step='1')
        with self.assertRaisesRegex(ValueError, '100'):
            generate_sweep_values(conditions)
        conditions.update(stop='1e100', step='1')
        with self.assertRaisesRegex(ValueError, '100'):
            generate_sweep_values(conditions)

    def test_capacitor_name_units_and_explicit_values(self):
        parsed = parse_parameter_sweep('CL을 1p부터 10p까지 1p 간격으로 바꿔가며 transient output swing과 gain 비교')
        self.assertEqual(parsed['component'], 'CL')
        self.assertEqual(parsed['measurements'], ['Voltage Gain', 'Output Swing'])
        self.assertEqual(len(generate_sweep_values(parsed)), 10)
        for text, expected in [('1p', 1e-12), ('2n', 2e-9), ('3µ', 3e-6), ('4m', .004), ('5k', 5000), ('6Meg', 6e6)]:
            self.assertEqual(float(component_value(text)), expected)
        self.assertEqual(generate_sweep_values(parse_parameter_sweep(REQUEST)), [1000, 2000, 5000])

    def test_official_component_edit_preserves_source(self):
        original = upload().getvalue()
        with tempfile.TemporaryDirectory() as directory:
            source, copy = Path(directory)/'original.asc', Path(directory)/'copy.asc'
            source.write_bytes(original)
            editor = AscEditor(source)
            edit_component_value(editor, 'r1', '2k')
            editor.save_netlist(copy)
            self.assertEqual(AscEditor(copy).get_component_value('R1'), '2k')
            self.assertEqual(AscEditor(copy).get_component_value('R2'), '1k')
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaises(ValueError):
                edit_component_value(editor, 'R10', '1k')

    def test_approval_and_missing_component_before_runner(self):
        runner = Mock()
        conditions = parse_parameter_sweep(REQUEST)
        with self.assertRaises(ValueError):
            run_parameter_sweep(upload(), conditions, AC, 'V(out)', 'V(in)', runner=runner)
        with self.assertRaises(ValueError):
            run_ltspice(upload(), AC, component_update=('R1', '2k'))
        conditions['component'] = 'R10'
        with self.assertRaises(ValueError):
            run_parameter_sweep(upload(), conditions, AC, 'V(out)', 'V(in)', approved=True, runner=runner)
        runner.assert_not_called()

    def test_partial_simulation_failure_table_and_metrics(self):
        runner = Mock(side_effect=[(Path('a.raw'), Path('a.log'), '.ac test'), RuntimeError('test failure'),
                                   (Path('c.raw'), Path('c.log'), '.ac test')])
        with patch('parameter_sweep_execution.measure_point', side_effect=[(object(), {'Gain [dB]': 10.}, []),
                                                                          (object(), {'Gain [dB]': 20.}, [])]):
            points = run_parameter_sweep(upload(), parse_parameter_sweep(REQUEST), AC, 'V(out)', 'V(in)', approved=True, runner=runner)
        self.assertEqual([point.status for point in points], ['OK', 'Simulation Failed', 'OK'])
        self.assertEqual(runner.call_count, 3)
        self.assertEqual([call.kwargs['component_update'][1] for call in runner.call_args_list], ['1E+3', '2E+3', '5E+3'])
        table = comparison_table(points, 'R1')
        self.assertIsNone(table[1]['Gain [dB]'])
        self.assertIn('test failure', table[1]['Notes'])
        summary = comparison_summary(points)[0]
        self.assertEqual(summary['Maximum at'], '5k')
        self.assertEqual(summary['Delta last-first'], 10.)
        self.assertEqual(summary['Valid points'], 2)
        graph = comparison_figures(points, 'R1')['Gain [dB]']
        self.assertTrue(np.isnan(graph.axes[0].lines[0].get_ydata()[1]))

    def test_analysis_failure_keeps_raw_and_continues(self):
        runner = Mock(return_value=(Path('kept.raw'), Path('kept.log'), '.ac test'))
        with patch('parameter_sweep_execution.measure_point', side_effect=[ValueError('missing trace'),
                  (object(), {'BW [Hz]': None}, ['Not found within sweep range']), (object(), {'BW [Hz]': 10.}, [])]):
            points = run_parameter_sweep(upload(), parse_parameter_sweep(REQUEST), AC, 'V(out)', 'V(in)', approved=True, runner=runner)
        self.assertEqual([point.status for point in points], ['Analysis Failed', 'Partial Measurements', 'OK'])
        self.assertEqual(points[0].raw, 'kept.raw')
        self.assertEqual(comparison_summary(points)[0]['Valid points'], 1)

    def test_overlay_limits_and_all_failed(self):
        result = Mock(frequency=np.array([10, 100]), gain_db=np.array([1, 2]))
        points = [SweepPoint(str(i), i, result=result) for i in range(10)]
        self.assertEqual(len(overlay_figure(points, 'R1', 'AC').axes[0].lines), 8)
        self.assertIsNone(overlay_figure([SweepPoint('1k', 1000)], 'R1', 'AC'))
        self.assertEqual(comparison_summary([SweepPoint('1k', 1000)]), [])

    def test_ui_forced_unapproved_event(self):
        before = {name: set((PROJECT/name).glob('**/*')) for name in ('simulation_input', 'simulation_output')}
        with patch('PyLTSpice.AscEditor') as editor, patch('PyLTSpice.SpiceEditor') as netlist, patch('PyLTSpice.SimRunner') as runner:
            app = AppTest.from_file(str(PROJECT/'app.py'), default_timeout=30).run()
            app.file_uploader[0].set_value(('test.asc', upload().getvalue(), 'text/plain')).run()
            app.text_area[0].set_value(REQUEST).run()
            app.button[0].click().run()
            original_button = st.button
            with patch('streamlit.button', side_effect=lambda label, **kwargs: True if label=='Run Parameter Sweep' else original_button(label, **kwargs)):
                app.run()
            self.assertFalse(app.exception)
            self.assertTrue(any('approve valid' in error.value for error in app.error))
            editor.assert_not_called()
            netlist.assert_not_called()
            runner.assert_not_called()
        for name, files in before.items():
            self.assertEqual(set((PROJECT/name).glob('**/*')), files)


if __name__ == '__main__':
    unittest.main()
