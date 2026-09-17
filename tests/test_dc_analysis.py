import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PyLTSpice import AscEditor

from ac_analysis import apply_analysis_directive
from ac_result_analysis import MissingTraceError
from dc_analysis import (is_dc_request, parse_dc_request, build_dc_directive, dc_value,
                         validate_sweep_source)
from dc_result_analysis import analyze_dc, read_dc_result, dc_figure


class DCParsingTests(unittest.TestCase):
    def test_examples_and_selected_point(self):
        text = 'V1을 0 V부터 5 V까지 10 mV 간격으로 sweep하고 V(out)을 보여줘.'
        self.assertTrue(is_dc_request(text))
        parsed = parse_dc_request(text)
        self.assertEqual([parsed[k] for k in ('analysis_type', 'sweep_source', 'dc_start', 'dc_stop', 'dc_step', 'target')],
                         ['DC Sweep', 'V1', '0 V', '5 V', '10 mV', 'V(out)'])
        parsed = parse_dc_request('V1을 0 V부터 5 V까지 10 mV 간격으로 sweep하고 I(M1)과 I(M2)의 차이와 matching error를 비교해줘.')
        self.assertEqual(parsed['dc_measurements'], ['Difference', 'Matching Error'])
        self.assertEqual(parsed['dc_comparison'], 'I(M2)')
        parsed = parse_dc_request('V1 = 3 V일 때 I(M1)을 구해줘.')
        self.assertEqual(parsed['dc_point'], '3 V')
        self.assertEqual(parsed['dc_measurements'], ['Value at Sweep Point'])
        self.assertEqual(parsed['dc_start'], '')  # no invented sweep range
        self.assertFalse(is_dc_request('AC 10 Hz to 1 MHz V(out) gain'))
        self.assertFalse(is_dc_request('AC sweep V1 from 10 Hz to 1 MHz, V(out) gain'))

    def test_english_units_negative_values_and_current_source(self):
        parsed = parse_dc_request('DC sweep I1 from 0 A to 1 mA step 10 uA; Id(M1) absolute difference Id(M2)')
        self.assertEqual(parsed['dc_comparison'], 'Id(M2)')
        self.assertEqual(parsed['dc_step'], '10 uA')
        self.assertEqual(parsed['dc_measurements'], ['Absolute Difference'])
        self.assertEqual(build_dc_directive('V1', '0 V', '5 V', '10 mV'), '.dc V1 0 5 10m')
        self.assertEqual(build_dc_directive('I1', '0 A', '1 mA', '10 µA'), '.dc I1 0 1m 10u')
        self.assertEqual(build_dc_directive('V1', '-1 V', '1 V', '100 mV'), '.dc V1 -1 1 100m')
        self.assertEqual(str(dc_value('1 MV', 'V')), '1E+6')

    def test_invalid_and_reversed_sweeps(self):
        for args in [('V1', '5', '0', '-1'), ('V1', '0', '0', '1'), ('V1', '0', '5', '0'),
                     ('V1', '0', '5', '-1'), ('V1', '0', '5', '6'), ('V1', '0 A', '5 V', '1'),
                     ('V1', 'NaN', '5', '1'), ('V1', '0', '1e999 V', '1'),
                     ('V1\n.tran 1', '0', '5', '1'), ('TEMP', '0', '5', '1'), ('V1', '', '5', '1')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_dc_directive(*args)

    def test_source_and_editor_copy(self):
        editor = Mock()
        editor.get_components.return_value = ['V1', 'I1']
        validate_sweep_source(editor, 'v1')
        with self.assertRaisesRegex(ValueError, 'Available independent sources'):
            validate_sweep_source(editor, 'Vmissing')
        source = 'Version 4\nSHEET 1 880 680\nTEXT 0 0 Left 2 !.tran 1m\nTEXT 0 40 Left 2 !.param R=1k\\n.ac dec 10 1 1Meg\nTEXT 0 80 Left 2 !.dc V2 0 2 1\n'
        with tempfile.TemporaryDirectory() as directory:
            original, copy = Path(directory)/'source.asc', Path(directory)/'copy.asc'
            original.write_text(source)
            schematic = AscEditor(original)
            apply_analysis_directive(schematic, '.dc V1 0 5 10m')
            schematic.save_netlist(copy)
            self.assertEqual(original.read_text(), source)
            result = copy.read_text()
            self.assertEqual(result.count('.dc '), 1)
            self.assertNotIn('.tran', result)
            self.assertNotIn('.ac ', result)
            self.assertIn('.param R=1k', result)


class DCResultTests(unittest.TestCase):
    def test_linear_interpolation_and_bounds(self):
        x = np.array([0, 1, 3, 5.])
        result = analyze_dc(x, 2*x+1, measurements=['Minimum', 'Maximum', 'Value at Sweep Point'], point=2)
        self.assertEqual(result.metrics['Minimum'], (1., 'V'))
        self.assertEqual(result.metrics['Maximum'], (11., 'V'))
        self.assertEqual(result.point_value, 5.)
        for point in (-1, 6, np.nan, None):
            with self.subTest(point=point), self.assertRaises(ValueError):
                analyze_dc(x, x, measurements=['Value at Sweep Point'], point=point)

    def test_signed_and_absolute_difference(self):
        x = np.arange(4.)
        result = analyze_dc(x, x, 2*x+1, ['Difference', 'Absolute Difference'])
        np.testing.assert_allclose(result.curves['Difference'][0], -x-1)
        np.testing.assert_allclose(result.curves['Absolute Difference'][0], x+1)

    def test_matching_definition_and_near_zero(self):
        x = np.arange(6.)
        first = np.array([0, 1e-15, 1e-12, .001, -.002, .003])
        result = analyze_dc(x, first, first*.9, ['Matching Error'], target_unit='A', comparison_unit='A')
        error = result.curves['Matching Error'][0]
        self.assertTrue(np.all(np.isnan(error[:3])))
        np.testing.assert_allclose(error[3:], 10.)
        self.assertTrue(any('Denominator: Target' in note for note in result.notes))
        all_zero = analyze_dc(x, np.zeros(6), np.ones(6), ['Matching Error'])
        self.assertEqual(all_zero.metrics, {})
        self.assertTrue(np.all(np.isnan(all_zero.curves['Matching Error'][0])))

    def test_invalid_data_and_units(self):
        for x in ([2, 1, 0], [0, 1, 1], [0, np.nan, 2], [0, 1, 0, 1]):
            with self.subTest(x=x), self.assertRaises(ValueError):
                analyze_dc(x, np.ones(len(x)))
        for y in ([0, np.inf, 2], [1, 2], [1j, 2j, 3j]):
            with self.subTest(y=y), self.assertRaises(ValueError):
                analyze_dc([0, 1, 2], y)
        with self.assertRaises(ValueError):
            analyze_dc([0, 1], [1, 2], [1, 2], ['Difference'], target_unit='V', comparison_unit='A')

    def test_missing_trace_no_fuzzy_mos_alias(self):
        raw = Mock()
        raw.get_raw_property.side_effect = lambda key: {'Plotname': 'DC transfer characteristic', 'Flags': 'real'}[key]
        raw.get_trace_names.return_value = ['v-sweep', 'Id(M1)', 'Id(M2)']
        with patch('dc_result_analysis.RawRead', return_value=raw), self.assertRaises(MissingTraceError) as caught:
            read_dc_result('unused.raw', 'I(M1)', 'I(M2)', sweep_source='V1')
        self.assertEqual(caught.exception.missing, ['I(M1)', 'I(M2)'])
        self.assertIn('Id(M1)', caught.exception.available)
        raw.get_trace.assert_not_called()

    def test_graph_and_overflow(self):
        result = analyze_dc([0, 1, 2], [1, 2, 3], [1, 1, 1], ['Difference', 'Matching Error', 'Value at Sweep Point'], 0.5)
        result.sweep_source = 'Vtest'
        fig = dc_figure(result)
        self.assertEqual(len(fig.axes), 3)
        self.assertEqual(fig.axes[0].get_xlabel(), 'Vtest [V]')
        self.assertEqual(len(fig.axes[0].lines), 3)
        result = analyze_dc([0, 1], [1e308, 1e308], [-1e308, -1e308], ['Difference', 'Matching Error'])
        self.assertFalse(result.metrics)


if __name__ == '__main__':
    unittest.main()
