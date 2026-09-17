import json
from pathlib import Path
import unittest

import numpy as np

from ac_result_analysis import analyze_ac, MissingTraceError
from transient_result_analysis import analyze_transient
from dc_result_analysis import analyze_dc
from parameter_sweep_execution import SweepPoint
from analysis_summary import build_analysis_summary, build_sweep_summary, json_native, summary_lines


GAIN = 'Low-Frequency Gain [dB]'
BW = '-3 dB Bandwidth [Hz]'


def ac_result(gain=6., bandwidth=100.):
    result = analyze_ac(np.logspace(0, 4, 101), np.ones(101)*2, np.ones(101))
    result.low_frequency_gain_db, result.threshold_db = gain, gain-3
    result.bandwidth_hz = bandwidth
    result.bandwidth_status = 'Found' if bandwidth is not None else 'Not found within sweep range'
    return result


def resistor_points():
    return [SweepPoint(label, value, 'OK' if bw is not None else 'Partial Measurements',
                       {GAIN: gain, BW: bw}, result=ac_result(gain, bw))
            for label, value, gain, bw in [('500',500,32.963,13129.), ('1k',1000,38.983,6275.),
                                         ('2k',2000,45.004,2613.), ('5k',5000,-38.216,None)]]


class AnalysisSummaryTests(unittest.TestCase):
    def test_ac_summary_and_evidence(self):
        result = ac_result()
        summary = build_analysis_summary('AC', result, conditions={'points': np.int64(100)},
                                         evidence={'raw_file':Path('test.raw'), 'applied_directive':'.ac dec 100 10 1Meg'})
        self.assertEqual(summary['measured_facts']['Low-Frequency Gain']['value'], 6.)
        self.assertEqual(summary['measured_facts']['-3 dB Level']['unit'], 'dB')
        self.assertEqual(summary['evidence']['raw_file'], 'test.raw')
        self.assertNotIn('transfer', json.dumps(summary))

    def test_transient_summary_not_applicable(self):
        t = np.linspace(0, 1, 5001)
        signal = np.sin(2*np.pi*10*t)
        result = analyze_transient(t, 3*signal, signal, ['Voltage Gain','Output Swing','Settling Time'])
        summary = build_analysis_summary('Transient', result)
        self.assertAlmostEqual(summary['measured_facts']['Voltage Gain']['Voltage Gain']['value'], 3., places=3)
        self.assertIn('Output Swing', summary['measured_facts'])
        self.assertTrue(any(w['code']=='measurement_not_applicable' for w in summary['warnings']))
        self.assertEqual(summary['measured_facts']['Settling Time'], {})

    def test_dc_summary_reuses_metrics(self):
        result = analyze_dc([0,1,2], [2,4,6], [1,2,3],
                            ['Minimum','Maximum','Value at Sweep Point','Difference','Matching Error'], .5)
        summary = build_analysis_summary('DC Sweep', result)
        self.assertEqual(summary['measured_facts']['Value at Sweep Point']['value'], 3)
        self.assertEqual(summary['measured_facts']['Matching Error Maximum']['value'], 50)
        self.assertEqual(summary['simulation_conditions']['selected_point'], .5)

    def test_bandwidth_not_found_is_null(self):
        summary = build_analysis_summary('AC', ac_result(bandwidth=None))
        self.assertIsNone(summary['measured_facts']['-3 dB Bandwidth']['value'])
        self.assertIn('bandwidth_not_found', [w['code'] for w in summary['warnings']])
        json.dumps(summary, allow_nan=False)

    def test_missing_measurement(self):
        result = analyze_dc([0,1], [0,0], [0,0], ['Matching Error'])
        summary = build_analysis_summary('DC Sweep', result, conditions={'measurements':['Matching Error']})
        self.assertEqual(summary['measured_facts'], {})
        self.assertIn('measurement_missing', [w['code'] for w in summary['warnings']])

    def test_missing_trace_and_simulation_error(self):
        summary = build_analysis_summary('AC', error=MissingTraceError(['V(missing)'], ['frequency','V(out)']))
        self.assertEqual(summary['warnings'][0]['code'], 'trace_missing')
        self.assertEqual(summary['warnings'][0]['available_traces'], ['frequency','V(out)'])
        failure = build_analysis_summary('AC', error=RuntimeError('model missing'), status='Simulation Failed')
        self.assertEqual(failure['warnings'][0]['code'], 'simulation_failed')

    def test_r1_sweep_segments_and_anomaly(self):
        points = resistor_points()
        summary = build_sweep_summary(points, 'R1', 'AC')
        gain = summary['derived_facts']['trends'][GAIN]
        self.assertEqual(gain['monotonic'], 'non_monotonic')
        segment = gain['segments'][0]
        self.assertEqual((segment['start_parameter'],segment['stop_parameter']), (500,2000))
        self.assertAlmostEqual(segment['delta'],12.041)
        self.assertIsNone(segment['relative_change_percent'])  # no percentage of dB
        bw = summary['derived_facts']['trends'][BW]
        self.assertEqual(bw['monotonic'], 'incomplete')
        self.assertEqual(bw['segments'][0]['direction'], 'decreasing')
        self.assertLess(bw['segments'][0]['relative_change_percent'], -80.)
        anomaly = next(w for w in summary['warnings'] if w['code']=='large_trend_reversal')
        self.assertEqual(anomaly['parameter_value'], 5000)
        self.assertEqual(anomaly['measurement'], GAIN)
        self.assertTrue(any(w['code']=='bandwidth_not_found' and w['parameter_value']==5000 for w in summary['warnings']))
        self.assertEqual(points[-1].metrics[BW], None)  # input not changed
        self.assertTrue(summary_lines(summary))

    def test_c1_monotonic_decrease_sorted_parameter(self):
        points = [SweepPoint(str(i),i*1e-9,'OK',{'Gain [V/V]':v}) for i,v in [(30,38.497),(10,68.365),(20,50.302)]]
        summary = build_sweep_summary(points, 'C1','Transient')
        trend = summary['derived_facts']['trends']['Gain [V/V]']
        self.assertEqual(trend['monotonic'], 'decreasing')
        self.assertEqual(trend['segments'][0]['point_count'], 3)
        self.assertFalse(any(w['code']=='large_trend_reversal' for w in summary['warnings']))

    def test_failed_point_and_gap_not_bridged(self):
        points = [SweepPoint('1',1,'OK',{'Gain':1}), SweepPoint('2',2,'Simulation Failed',{'Gain':999},['failure']),
                  SweepPoint('3',3,'OK',{'Gain':3})]
        summary = build_sweep_summary(points,'R1','AC')
        self.assertEqual(summary['measured_facts']['points'][1]['measurements'], {})
        self.assertEqual(summary['derived_facts']['trends']['Gain']['segments'], [])
        self.assertEqual(summary['comparison_results']['extrema_and_changes'][0]['Maximum'], 3)
        self.assertEqual(summary['warnings'][0]['code'], 'simulation_failed')

    def test_nonfinite_strict_json_and_no_mutation(self):
        result = ac_result()
        result.low_frequency_gain_db = np.float64(np.nan)
        summary = build_analysis_summary('AC', result)
        self.assertIsNone(summary['measured_facts']['Low-Frequency Gain']['value'])
        self.assertTrue(np.isnan(result.low_frequency_gain_db))
        warnings = []
        self.assertEqual(json_native(np.array([1.,np.inf]),warnings), [1.,None])
        self.assertEqual(warnings[0]['path'], '$[1]')
        self.assertIs(type(json_native(np.int64(3))),int)
        json.loads(json.dumps(summary, allow_nan=False))

    def test_duplicates_and_tiny_reversal(self):
        points = [SweepPoint(str(i),i,'OK',{'gain':v}) for i,v in enumerate([1.,2.,3.,2.5])]
        summary = build_sweep_summary(points,'R1','AC')
        self.assertFalse(any(w['code']=='large_trend_reversal' for w in summary['warnings']))
        points[2].value = 1
        summary = build_sweep_summary(points,'R1','AC')
        self.assertEqual(summary['derived_facts']['trends'], {})
        self.assertIn('trend_not_evaluated',[w['code'] for w in summary['warnings']])

    def test_constant_zero_and_no_points(self):
        points = [SweepPoint(str(i),i,'OK',{'gain':0.}) for i in range(3)]
        trend = build_sweep_summary(points,'R1','AC')['derived_facts']['trends']['gain']
        self.assertEqual(trend['monotonic'],'constant')
        self.assertIsNone(trend['segments'][0]['relative_change_percent'])
        empty = build_sweep_summary([],'R1','AC')
        self.assertEqual(empty['measured_facts']['points'],[])
        self.assertTrue(empty['warnings'])

    def test_sweep_trace_failure_details(self):
        point = SweepPoint('1k',1000,'Analysis Failed',raw='kept.raw',log='kept.log',
                           failure={'message':'Trace not found', 'missing_traces':['V(x)'], 'available_traces':['V(out)']})
        summary = build_sweep_summary([point],'R1','AC')
        warning = next(w for w in summary['warnings'] if w['code']=='trace_missing')
        self.assertEqual(warning['missing_traces'], ['V(x)'])
        self.assertEqual(warning['available_traces'], ['V(out)'])
        self.assertEqual(summary['evidence']['points'][0]['raw_file'], 'kept.raw')

    def test_nonfinite_sweep_and_tolerance(self):
        points = [SweepPoint(str(i),i,'OK',{'Gain':v}) for i,v in enumerate([1., np.inf, 2.])]
        summary = build_sweep_summary(points,'R1','AC')
        self.assertEqual(summary['derived_facts']['trends']['Gain']['segments'], [])
        self.assertEqual(summary['comparison_results']['extrema_and_changes'][0]['Maximum'], 2.)
        self.assertTrue(any(w['code']=='non_finite_result' for w in summary['warnings']))
        json.dumps(summary,allow_nan=False)
        points = [SweepPoint(str(i),i,'OK',{'Gain':v}) for i,v in enumerate([1.,1.+1e-10,1.-1e-10])]
        self.assertEqual(build_sweep_summary(points,'R1','AC')['derived_facts']['trends']['Gain']['monotonic'],'constant')


if __name__ == '__main__':
    unittest.main()
