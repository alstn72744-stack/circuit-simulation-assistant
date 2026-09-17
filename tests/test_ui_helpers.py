import copy
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from streamlit.testing.v1 import AppTest

from ui_helpers import (human_value, trace_suggestion, asc_voltage_traces, review_defaults,
                        compact_comparison_rows, compact_extrema_rows, style_graph,
                        GRAPH_WIDTH_FRACTION, GRAPH_DPI)
from ac_result_analysis import analyze_ac, gain_figure, MissingTraceError
from transient_result_analysis import analyze_transient, waveform_figure
from dc_result_analysis import analyze_dc, dc_figure
from parameter_sweep_execution import SweepPoint, comparison_table, comparison_figures, overlay_figure
from analysis_summary import build_sweep_summary
from dc_analysis import parse_dc_request

PROJECT = Path(__file__).resolve().parents[1]
PREVIOUS = dict(target='V(vout)',reference='V(vin)',start_frequency='10 Hz',stop_frequency='1 MHz',points=100,sweep_type='Decade')
DC_REQUEST = ('V2를 3.4 V부터 3.7 V까지 0.01 V 간격으로 DC sweep하고 '
              'V(vout)의 변화를 보여줘. 3.55 V에서의 V(vout)도 구해줘.')


class UIHelperTests(unittest.TestCase):
    def test_exact_dc_request_separates_source_range_and_point(self):
        parsed = parse_dc_request(DC_REQUEST)
        self.assertEqual([parsed[k] for k in ('sweep_source','dc_start','dc_stop','dc_step','dc_point','target')],
                         ['V2','3.4 V','3.7 V','0.01 V','3.55 V','V(vout)'])
        self.assertIn('Value at Sweep Point',parsed['dc_measurements'])
        self.assertEqual(parse_dc_request('3.55 V에서의 V(vout)도 구해줘')['sweep_source'],'')

    def test_trace_exact_case_and_simple_name(self):
        self.assertIsNone(trace_suggestion('V(vout)',['V(vout)']))
        self.assertEqual(trace_suggestion('v(VOUT)',['V(vout)']),'V(vout)')
        self.assertEqual(trace_suggestion('V(out)',['V(vin)','V(vout)']),'V(vout)')
        self.assertEqual(trace_suggestion('V(vout)',['V(out)']),'V(out)')

    def test_ambiguous_missing_empty_and_current_not_guessed(self):
        for requested, names in [('V(out)',['V(vout)','V(VOUT)']), ('V(output)',['V(vout)']),
                                 ('I(M1)',['Id(M1)']), ('',['V(vout)']), ('V(out)',[])]:
            self.assertIsNone(trace_suggestion(requested,names))

    def test_asc_label_inventory_encoding_and_no_mutation(self):
        text = 'Version 4\nFLAG 1 2 vout\nFLAG -1 2 vin\nFLAG 0 0 0\nFLAG 1 2 vout\n'
        for encoding in ('utf-8','utf-16','latin-1'):
            data = text.encode(encoding)
            self.assertEqual(asc_voltage_traces(data),['V(vout)','V(vin)'])
            self.assertEqual(data,text.encode(encoding))

    def test_ac_reuse_omitted_conditions_without_mutation(self):
        original = dict(PREVIOUS)
        values, reused = review_defaults('R1을 1k, 2k로 바꿔가며 AC simulation gain 비교','AC',PREVIOUS)
        for key,value in PREVIOUS.items():
            self.assertEqual(values[key],value)
            self.assertIn(key,reused)
        self.assertEqual(PREVIOUS,original)

    def test_explicit_range_target_reference_points_sweep_override(self):
        values, reused = review_defaults('AC V(newout) V(newin) 20 Hz to 2 MHz points=50 octave gain','AC',PREVIOUS)
        self.assertEqual([values[k] for k in PREVIOUS],['V(newout)','V(newin)','20 Hz','2 MHz',50,'Octave'])
        self.assertEqual(reused,[])

    def test_partial_override_and_reference_only(self):
        values,reused = review_defaults('AC Stop Frequency = 3 MHz Reference=V(newin)','AC',PREVIOUS)
        self.assertEqual(values['target'],'V(vout)')
        self.assertEqual(values['reference'],'V(newin)')
        self.assertEqual(values['start_frequency'],'10 Hz')
        self.assertEqual(values['stop_frequency'],'3 MHz')
        self.assertNotIn('reference',reused)

    def test_no_history_no_invented_frequency(self):
        values,reused = review_defaults('AC gain','AC')
        self.assertEqual(values['stop_frequency'],'')
        self.assertEqual(reused,[])

    def test_transient_and_dc_reuse_with_explicit_override(self):
        values,_ = review_defaults('Transient for 2 ms V(new)','Transient',
            dict(target='V(old)',reference='V(in)',stop_time='1 ms',maximum_timestep='1 us',start_saving_time=''))
        self.assertEqual(values['stop_time'],'2 ms')
        self.assertEqual(values['target'],'V(new)')
        self.assertEqual(values['reference'],'V(in)')
        values,_ = review_defaults('3.55 V에서의 V(vout)도 구해줘','DC Sweep',
            dict(target='V(old)',sweep_source='V2',dc_start='0 V',dc_stop='5 V',dc_step='10 mV'))
        self.assertEqual(values['dc_point'],'3.55 V')
        self.assertEqual(values['sweep_source'],'V2')
        self.assertIn('Value at Sweep Point',values['dc_measurements'])

    def test_human_units_and_unavailable(self):
        for value,unit,expected in [(13129.469,'Hz','13.129 kHz'),(6274.788,'Hz','6.275 kHz'),
                (.0199997,'V','20.000 mV'),(-.000321,'A','-321.000 µA'),(0,'V','0.000 V'),
                (38.9834,'dB','38.983 dB'),(.9999999,'V','1.000 V'),(1e-15,'A','1.000e-15 A')]:
            self.assertEqual(human_value(value,unit),expected)
        for value in (None,float('nan'),float('inf')):
            self.assertEqual(human_value(value,'Hz'),'Not available')

    def test_table_formatting_is_copy_and_hides_paths(self):
        rows = comparison_table([SweepPoint('1k',1000,'OK',{'BW [Hz]':6274.788},raw='C:/private/file.raw',log='C:/private/file.log')],'R1')
        original = copy.deepcopy(rows)
        display = compact_comparison_rows(rows)
        self.assertEqual(display[0]['BW'],'6.275 kHz')
        self.assertNotIn('RAW',display[0])
        self.assertNotIn('LOG',display[0])
        self.assertEqual(rows,original)
        extrema = [{'Measurement':'BW [Hz]','Minimum':6274.788,'Maximum':13129.469,'Delta last-first':-6854.681}]
        before = copy.deepcopy(extrema)
        self.assertEqual(compact_extrema_rows(extrema)[0]['Maximum'],'13.129 kHz')
        self.assertEqual(extrema,before)

    def test_all_graphs_preserve_ratio_and_render_with_legible_fonts(self):
        ac = analyze_ac(np.logspace(1,6,201),np.ones(201)*2,np.ones(201))
        t = np.linspace(0,.01,1001)
        transient = analyze_transient(t,np.sin(2*np.pi*1000*t),np.sin(2*np.pi*1000*t))
        dc = analyze_dc(np.arange(5.),np.arange(5.),measurements=['Minimum','Maximum'])
        dc.sweep_source='V1'
        points = [SweepPoint('1k',1000,'OK',{'Gain [dB]':6.},result=ac),SweepPoint('2k',2000,'OK',{'Gain [dB]':8.},result=ac)]
        figures = [gain_figure(ac),waveform_figure(transient),dc_figure(dc),*comparison_figures(points,'R1').values(),overlay_figure(points,'R1','AC')]
        for figure in figures:
            ratio = figure.get_figwidth()/figure.get_figheight()
            buffer = io.BytesIO()
            style_graph(figure).savefig(buffer,format='png',dpi=GRAPH_DPI)
            with Image.open(buffer) as image:
                self.assertAlmostEqual(image.width/image.height,ratio,places=2)
            self.assertGreaterEqual(figure.axes[0].xaxis.label.get_fontsize(),11)
        self.assertTrue(.8 <= GRAPH_WIDTH_FRACTION <= .85)


class CoreUXUITests(unittest.TestCase):
    def button(self,app,label):
        return next(b for b in app.button if b.label==label)

    def prepare(self,request='AC V(out) V(in) 10 Hz to 1 MHz gain', data=None):
        app=AppTest.from_file(str(PROJECT/'app.py'),default_timeout=45).run()
        self.data=data or (PROJECT/'tests/fixtures/dc_divider.asc').read_bytes()
        app.file_uploader[0].set_value(('circuit.asc',self.data,'text/plain')).run()
        app.text_area[0].set_value(request).run()
        self.button(app,'Analyze Request').click().run()
        return app

    def test_suggestion_requires_click_and_resets_approval(self):
        data=(PROJECT/'tests/fixtures/dc_divider.asc').read_bytes().replace(b' out',b' vout')
        with patch('simulation_runner.run_ltspice') as runner:
            app=self.prepare(data=data)
            self.assertTrue(any('Did you mean V(vout)?' in w.value for w in app.warning))
            self.assertEqual(app.text_input(key='review_target').value,'V(out)')
            app.checkbox(key='execution_approved').check().run()
            self.button(app,'Use V(vout) for Target').click().run()
            self.assertEqual(app.text_input(key='review_target').value,'V(vout)')
            self.assertFalse(app.checkbox(key='execution_approved').value)
            self.assertTrue(self.button(app,'Run Simulation').disabled)
            runner.assert_not_called()
            self.assertFalse(app.exception)

    def test_successful_ac_to_sweep_reuse_new_override_and_other_circuit(self):
        result=analyze_ac(np.logspace(1,6,101),np.ones(101)*2,np.ones(101))
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/'run.raw'
            with patch('simulation_runner.run_ltspice',return_value=(raw,raw.with_suffix('.log'),'.ac dec 100 10 1Meg')) as runner, patch('ac_result_analysis.read_ac_result',return_value=result):
                data=(PROJECT/'tests/fixtures/dc_divider.asc').read_bytes().replace(b' out',b' vout').replace(b' in',b' vin')
                app=self.prepare('AC V(vout) V(vin) 10 Hz to 1 MHz gain', data=data)
                app.checkbox(key='execution_approved').check().run()
                self.button(app,'Run Simulation').click().run()
                app.text_area[0].set_value('Transient voltage gain').run()
                self.button(app,'Analyze Request').click().run()
                self.assertEqual(app.text_input(key='review_target').value,'')
                self.assertEqual(app.text_input(key='review_reference').value,'')
                self.assertEqual(app.text_input(key='review_stop_time').value,'')
                app.text_area[0].set_value('R1을 1k, 2k로 바꿔가며 AC gain 비교').run()
                self.button(app,'Analyze Request').click().run()
                self.assertEqual(app.text_input(key='review_target').value,'V(vout)')
                self.assertEqual(app.text_input(key='review_reference').value,'V(vin)')
                self.assertEqual(app.text_input(key='review_stop_frequency').value,'1 MHz')
                self.assertTrue(self.button(app,'Run Parameter Sweep').disabled)
                self.assertEqual(runner.call_count,1)
                app.text_area[0].set_value('R1을 1k, 2k로 바꿔가며 AC V(new) 20 Hz to 2 MHz points=50').run()
                self.button(app,'Analyze Request').click().run()
                self.assertEqual(app.text_input(key='review_target').value,'V(new)')
                self.assertEqual(app.text_input(key='review_reference').value,'V(vin)')
                self.assertEqual(app.number_input(key='review_points').value,50)
                app.file_uploader[0].set_value(('different.asc',self.data+b'\nTEXT 0 0 Left 2 ;different\n','text/plain')).run()
                app.text_area[0].set_value('AC gain').run()
                self.button(app,'Analyze Request').click().run()
                self.assertEqual(app.text_input(key='review_stop_frequency').value,'')
                self.assertFalse(app.exception)

    def test_failure_does_not_seed_reuse_and_raw_suggestion_shown(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/'run.raw'
            with patch('simulation_runner.run_ltspice',return_value=(raw,raw.with_suffix('.log'),'.ac dec 100 10 1Meg')), patch('ac_result_analysis.read_ac_result',side_effect=MissingTraceError(['V(out)'],['V(vout)','V(in)'])):
                app=self.prepare()
                app.checkbox(key='execution_approved').check().run()
                self.button(app,'Run Simulation').click().run()
                self.assertTrue(any('RAW traces. Did you mean V(vout)?' in w.value for w in app.warning))
                self.assertEqual(app.text_input(key='review_target').value,'V(out)')
                self.assertFalse(any(history for history in app.session_state['successful_review_conditions'].values()))
                self.assertFalse(app.exception)

    def test_dc_point_card_uses_existing_interpolation(self):
        result=analyze_dc(np.array([0.,3.,4.,5.]),np.array([3.14,4.94,5.54,6.14]),measurements=['Minimum','Maximum','Value at Sweep Point'],point=3.55)
        result.sweep_source='V2'
        result.target_name='V(vout)'
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/'run.raw'
            with patch('simulation_runner.run_ltspice',return_value=(raw,raw.with_suffix('.log'),'.dc V2 0 5 100m')), patch('dc_result_analysis.read_dc_result',return_value=result) as reader:
                app=self.prepare(DC_REQUEST)
                self.assertEqual(app.text_input(key='review_dc_point').value,'3.55 V')
                app.checkbox(key='execution_approved').check().run()
                self.button(app,'Run Simulation').click().run()
                card=next(m for m in app.metric if m.label=='Value at V2 = 3.55 V')
                self.assertEqual(card.value,'5.270 V')
                self.assertEqual(reader.call_args.args[-1],3.55)
                self.assertEqual(app.session_state['completed_analysis_summary']['measured_facts']['Value at Sweep Point']['value'],result.point_value)
                self.assertFalse(app.exception)

    def test_point_evidence_survives_rerun_and_summary_precision(self):
        points=[SweepPoint('1k',1000,'OK',{'BW [Hz]':6274.787804816243},raw='C:/long/path/run.raw',log='C:/long/path/run.log',directive='.ac dec 100 10 1Meg')]
        summary=build_sweep_summary(points,'R1','AC')
        before=copy.deepcopy(summary)
        app=AppTest.from_file(str(PROJECT/'app.py')).run()
        app.session_state['completed_analysis_summary']=summary
        app.run()
        self.assertTrue(any('Point Details / Evidence'==e.label for e in app.expander))
        self.assertTrue(any('C:/long/path/run.raw' in t.value for t in app.text))
        self.assertTrue(any('C:/long/path/run.log' in t.value for t in app.text))
        app.run()
        self.assertEqual(app.session_state['completed_analysis_summary'],before)
        self.assertFalse(app.exception)


if __name__=='__main__':
    unittest.main()
