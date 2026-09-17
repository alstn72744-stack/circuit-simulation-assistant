from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from parameter_sweep import (parse_parameter_sweep, is_parameter_sweep_request,
                             validate_parameter_sweep, component_value,
                             validate_asc_component, ComponentNotFoundError)

REQUEST = 'R1을 1k, 2k, 5k, 10k로 바꿔가며 AC simulation하고 gain과 -3 dB bandwidth를 비교해줘.'
RANGE_REQUEST = 'R1을 1k부터 10k까지 1k 간격으로 sweep해줘.'
PROJECT = Path(__file__).resolve().parents[1]
ASC = (PROJECT/'tests/fixtures/dc_divider.asc').read_bytes()


class ParameterComponentTests(unittest.TestCase):
    def test_existing_component(self):
        self.assertEqual(validate_asc_component(ASC, 'R1'), 'R1')

    def test_missing_component_no_fuzzy_match(self):
        with self.assertRaises(ComponentNotFoundError) as caught:
            validate_asc_component(ASC, 'R10')
        self.assertIn('R10', str(caught.exception))
        self.assertEqual(caught.exception.available, ['V1', 'R1', 'R2'])

    def test_case_insensitive_component(self):
        self.assertEqual(validate_asc_component(ASC, ' r1 '), 'R1')

    def test_empty_component(self):
        for name in ('', '   '):
            with self.subTest(name=name), self.assertRaises(ComponentNotFoundError) as caught:
                validate_asc_component(ASC, name)
            self.assertIn('empty', str(caught.exception))

    def test_encoding_and_comment_records(self):
        text = ASC.decode('utf-8') + '\nTEXT 0 0 Left 2 ;SYMATTR InstName R99\n'
        for encoding in ('utf-8-sig', 'utf-16', 'cp949'):
            data = (text + 'TEXT 0 320 Left 2 ;회로 설명\n').encode(encoding)
            self.assertEqual(validate_asc_component(data, 'R2'), 'R2')
            with self.assertRaises(ComponentNotFoundError):
                validate_asc_component(data, 'R99')
        with self.assertRaisesRegex(ValueError, 'ASC header'):
            validate_asc_component(b'not an ASC', 'R1')


class ParameterParsingTests(unittest.TestCase):
    def test_explicit_values(self):
        parsed = parse_parameter_sweep(REQUEST)
        self.assertTrue(is_parameter_sweep_request(REQUEST))
        self.assertEqual(parsed['sweep_type'], 'Component Value')
        self.assertEqual(parsed['values'], ['1k', '2k', '5k', '10k'])
        validate_parameter_sweep(parsed)

    def test_range(self):
        parsed = parse_parameter_sweep(RANGE_REQUEST)
        self.assertEqual([parsed[key] for key in ('component', 'start', 'stop', 'step')], ['R1', '1k', '10k', '1k'])
        self.assertEqual(parsed['values'], [])
        self.assertEqual(parsed['analysis_type'], 'Not specified')
        parsed['analysis_type'] = 'AC'
        validate_parameter_sweep(parsed)

    def test_component_names_and_routing(self):
        for name in ('R12', 'c2', 'L3'):
            self.assertEqual(parse_parameter_sweep(REQUEST.replace('R1', name))['component'], name.upper())
        for normal in ('AC sweep 10 Hz to 1 MHz I(R1) gain',
                       'V1을 0 V부터 5 V까지 10 mV 간격으로 sweep하고 I(R1)을 보여줘',
                       'V(out) transient for 1 ms'):
            self.assertFalse(is_parameter_sweep_request(normal))
        self.assertTrue(is_parameter_sweep_request('parameter sweep values 1k, 2k'))
        self.assertEqual(parse_parameter_sweep('parameter sweep values 1k, 2k')['component'], '')

    def test_analysis_types(self):
        for analysis, expected in [('AC', 'AC'), ('Transient', 'Transient'), ('DC', 'DC Sweep')]:
            self.assertEqual(parse_parameter_sweep(REQUEST.replace('AC', analysis))['analysis_type'], expected)

    def test_measurements(self):
        self.assertEqual(parse_parameter_sweep(REQUEST)['measurements'], ['Gain', '-3 dB Bandwidth'])
        transient = 'C2를 1n, 2n로 바꿔가며 Transient simulation rise time과 overshoot 비교'
        self.assertEqual(parse_parameter_sweep(transient)['measurements'], ['Rise Time', 'Overshoot'])

    def test_invalid_inputs_and_units(self):
        for text in (REQUEST.replace('2k', 'bad'), REQUEST.replace('2k', ''),
                     REQUEST.replace('1k, 2k, 5k, 10k', '1k'), REQUEST.replace('R1', 'M1'),
                     REQUEST.replace('1k', '0'), REQUEST.replace('1k', '-1k'),
                     RANGE_REQUEST.replace('10k', '500'), RANGE_REQUEST.replace('1k 간격', '0 간격'),
                     RANGE_REQUEST.replace('1k 간격', '20k 간격')):
            parsed = parse_parameter_sweep(text)
            parsed['analysis_type'] = 'AC'
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_parameter_sweep(parsed)
        for value in ('nan', '1e9999', '1k\n.step x', '{R}', '1e-9999'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                component_value(value)
        self.assertEqual(component_value('1M'), component_value('1m'))
        self.assertEqual(component_value('1Meg'), 1000000)


class ParameterReviewTests(unittest.TestCase):
    def configure_ac(self, app):
        for key, value in [('review_target', 'V(out)'), ('review_reference', 'V(in)'),
                           ('review_start_frequency', '10 Hz'), ('review_stop_frequency', '1 MHz')]:
            app.text_input(key=key).set_value(value).run()

    def prepare(self, app, request):
        app.file_uploader[0].set_value(('review.asc', ASC, 'text/plain')).run()
        app.text_area[0].set_value(request).run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(button.label == 'Run Simulation' for button in app.button))

    def test_approval_and_edits_never_execute(self):
        before = {folder: set((PROJECT/folder).glob('**/*')) for folder in ('simulation_input', 'simulation_output')}
        with patch('PyLTSpice.AscEditor') as editor, patch('PyLTSpice.SpiceEditor') as netlist, patch('PyLTSpice.SimRunner') as runner:
            app = AppTest.from_file(str(PROJECT/'app.py'), default_timeout=30).run()
            self.prepare(app, REQUEST)
            self.configure_ac(app)
            self.assertEqual(app.text_input(key='parameter_values').value, '1k, 2k, 5k, 10k')
            self.assertEqual(app.multiselect[0].value, ['Gain', '-3 dB Bandwidth'])
            self.assertEqual(app.success[0].value, 'Component found: R1')
            app.checkbox(key='parameter_approved').check().run()
            self.assertFalse(next(button for button in app.button if button.label == 'Run Parameter Sweep').disabled)
            self.assertFalse(any(button.label == 'Run Simulation' for button in app.button))
            for key, value in [('parameter_component', 'R2'), ('parameter_values', '2k, 4k')]:
                app.text_input(key=key).set_value(value).run()
                self.assertFalse(app.checkbox(key='parameter_approved').value)
                app.checkbox(key='parameter_approved').check().run()
            app.text_input(key='parameter_component').set_value('R10').run()
            self.assertTrue(app.checkbox(key='parameter_approved').disabled)
            self.assertFalse(app.checkbox(key='parameter_approved').value)
            self.assertTrue(any('Component not found: R10' in item.value for item in app.error))
            self.assertIn('R1', app.code[0].value)
            app.text_input(key='parameter_component').set_value('r1').run()
            self.assertEqual(app.success[0].value, 'Component found: R1')
            self.assertFalse(app.checkbox(key='parameter_approved').disabled)
            app.text_input(key='parameter_component').set_value('').run()
            self.assertTrue(app.checkbox(key='parameter_approved').disabled)
            app.text_input(key='parameter_component').set_value('R1').run()
            app.text_input(key='parameter_values').set_value('2k, bad').run()
            self.assertTrue(app.checkbox(key='parameter_approved').disabled)
            self.assertTrue(app.error)
            self.assertFalse(app.exception)
            self.assertEqual((PROJECT/'tests/fixtures/dc_divider.asc').read_bytes(), ASC)
            editor.assert_not_called()
            netlist.assert_not_called()
            runner.assert_not_called()
            for folder, files in before.items():
                self.assertEqual(set((PROJECT/folder).glob('**/*')), files)

    def test_range_and_return_to_existing_review(self):
        with patch('PyLTSpice.AscEditor') as editor, patch('PyLTSpice.SpiceEditor') as netlist, patch('PyLTSpice.SimRunner') as runner:
            app = AppTest.from_file(str(PROJECT/'app.py'), default_timeout=30).run()
            self.prepare(app, RANGE_REQUEST)
            self.assertEqual(app.text_input(key='parameter_stop').value, '10k')
            self.assertTrue(app.checkbox(key='parameter_approved').disabled)
            app.selectbox(key='parameter_analysis_type').set_value('AC').run()
            self.configure_ac(app)
            app.text_input(key='parameter_stop').set_value('20k').run()
            app.checkbox(key='parameter_approved').check().run()
            self.assertFalse(next(button for button in app.button if button.label == 'Run Parameter Sweep').disabled)
            app.selectbox(key='parameter_value_mode').set_value('Explicit Values').run()
            self.assertFalse(app.checkbox(key='parameter_approved').value)
            app.text_input(key='parameter_values').set_value('1k, 3k').run()
            self.assertFalse(app.checkbox(key='parameter_approved').disabled)
            for request, analysis in [('AC 10 Hz to 1 MHz V(out) gain', 'AC'),
                                      ('V(out) transient for 1 ms', 'Transient'),
                                      ('V1을 0 V부터 5 V까지 10 mV 간격으로 sweep하고 V(out)을 보여줘', 'DC Sweep')]:
                app.text_area[0].set_value(request).run()
                app.button[0].click().run()
                self.assertEqual(app.selectbox(key='review_analysis_type').value, analysis)
                self.assertTrue(next(button for button in app.button if button.label == 'Run Simulation').disabled)
                self.assertFalse(app.exception)
            editor.assert_not_called()
            netlist.assert_not_called()
            runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()
